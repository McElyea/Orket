from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Protocol

from orket.adapters.storage.async_file_tools import capture_file_roots
from orket.runtime.execution.packet2_receipt_observation import (
    _normalize_turn_index,
    observe_packet2_file,
    observe_packet2_receipts,
)
from orket.runtime.execution.source_attribution_receipt import observe_source_receipt
from orket.runtime.idempotency_discipline_policy import idempotency_discipline_policy_snapshot
from orket.runtime.run_summary_artifact_provenance import normalize_artifact_provenance_facts

SOURCE_ATTRIBUTION_RECEIPT_PATH = "agent_output/source_attribution_receipt.json"
_SOURCE_ATTRIBUTION_REQUIRED_CLAIM_FIELDS = ("claim_id", "claim", "source_ids")
_SOURCE_ATTRIBUTION_REQUIRED_SOURCE_FIELDS = ("source_id", "title", "uri", "kind")
_NARRATION_EFFECT_TOOLS = {"update_issue_status", "write_file"}


class _CardHistoryRepository(Protocol):
    async def get_card_history(self, card_id: str) -> list[str]: ...


def normalize_truthful_runtime_policy(payload: Any) -> dict[str, Any]:
    policy = {
        "configured": False,
        "source_attribution_mode": "optional",
        "high_stakes": False,
    }
    if not isinstance(payload, dict):
        return policy
    policy["configured"] = True
    mode = str(payload.get("source_attribution_mode") or "").strip().lower()
    if mode in {"optional", "required"}:
        policy["source_attribution_mode"] = mode
    policy["high_stakes"] = bool(payload.get("high_stakes"))
    if policy["source_attribution_mode"] == "required":
        policy["high_stakes"] = True
    return policy


async def collect_phase_c_packet2_facts(
    *,
    workspace: Path,
    run_id: str,
    cards_repo: _CardHistoryRepository,
    policy: dict[str, Any] | None = None,
    artifact_provenance_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    captured_workspace, = capture_file_roots([workspace])
    captured_run_id = str(run_id)
    normalized_policy = normalize_truthful_runtime_policy(policy)
    normalized_provenance = normalize_artifact_provenance_facts(artifact_provenance_facts)
    receipts = await observe_packet2_receipts(workspace=captured_workspace, run_id=captured_run_id)
    narration_facts = await _collect_narration_effect_audit_facts(
        workspace=captured_workspace,
        receipts=receipts,
        cards_repo=cards_repo,
    )
    source_attribution_facts = await collect_source_attribution_facts(
        workspace=captured_workspace,
        policy=normalized_policy,
        artifact_provenance_facts=normalized_provenance,
    )
    idempotency_facts = _collect_idempotency_facts(receipts=receipts)
    packet2_facts: dict[str, Any] = {}
    if narration_facts:
        packet2_facts["narration_to_effect_audit"] = narration_facts
    if idempotency_facts:
        packet2_facts["idempotency"] = idempotency_facts
    if source_attribution_facts:
        packet2_facts["source_attribution"] = source_attribution_facts
    return packet2_facts


async def collect_source_attribution_facts(
    *,
    workspace: Path,
    policy: dict[str, Any] | None = None,
    artifact_provenance_facts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_policy = normalize_truthful_runtime_policy(policy)
    receipt_path = Path(workspace) / SOURCE_ATTRIBUTION_RECEIPT_PATH
    provenance_entry = _source_receipt_provenance_entry(artifact_provenance_facts)
    exists, payload, invalid_json = await observe_source_receipt(receipt_path)
    should_emit = bool(normalized_policy.get("configured")) or exists or provenance_entry is not None
    if not should_emit:
        return {}

    missing_requirements: list[str] = []
    claims: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    if not exists:
        missing_requirements.append("source_attribution_receipt_missing")
    else:
        if invalid_json:
            missing_requirements.append("source_attribution_receipt_invalid_json")
        if isinstance(payload, dict):
            claims = _normalize_source_attribution_claims(payload.get("claims"))
            sources = _normalize_source_attribution_sources(payload.get("sources"))
            if not claims:
                missing_requirements.append("source_attribution_claims_missing")
            if not sources:
                missing_requirements.append("source_attribution_sources_missing")
            if claims and sources:
                source_ids = {str(row["source_id"]) for row in sources}
                if any(not set(row.get("source_ids") or []).issubset(source_ids) for row in claims):
                    missing_requirements.append("source_attribution_claim_source_missing")
            if claims and any(set(row.keys()) != set(_SOURCE_ATTRIBUTION_REQUIRED_CLAIM_FIELDS) for row in claims):
                missing_requirements.append("source_attribution_claims_missing")
            if sources and any(set(row.keys()) != set(_SOURCE_ATTRIBUTION_REQUIRED_SOURCE_FIELDS) for row in sources):
                missing_requirements.append("source_attribution_source_fields_missing")
        elif not invalid_json:
            missing_requirements.extend(["source_attribution_claims_missing", "source_attribution_sources_missing"])

    missing_requirements = sorted(set(missing_requirements))
    mode = str(normalized_policy.get("source_attribution_mode") or "optional")
    blocked = mode == "required" and bool(missing_requirements)
    if blocked:
        synthesis_status = "blocked"
    elif missing_requirements:
        synthesis_status = "optional_unverified"
    else:
        synthesis_status = "verified"
    facts: dict[str, Any] = {
        "mode": mode,
        "high_stakes": bool(normalized_policy.get("high_stakes")),
        "synthesis_status": synthesis_status,
        "claim_count": len(claims),
        "source_count": len(sources),
        "missing_requirements": missing_requirements,
        "artifact_provenance_verified": provenance_entry is not None,
        "receipt_artifact_path": SOURCE_ATTRIBUTION_RECEIPT_PATH,
    }
    if claims:
        facts["claims"] = claims
    if sources:
        facts["sources"] = sources
    if isinstance(provenance_entry, dict):
        operation_id = str(provenance_entry.get("operation_id") or "").strip()
        if operation_id:
            facts["receipt_operation_id"] = operation_id
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(provenance_entry.get(field) or "").strip()
            if token:
                facts[field] = token
    return facts


def resolve_source_attribution_gate_failure_reason(
    source_attribution_facts: dict[str, Any],
) -> str | None:
    if str(source_attribution_facts.get("synthesis_status") or "") != "blocked":
        return None
    missing_requirements = list(source_attribution_facts.get("missing_requirements") or [])
    for token in missing_requirements:
        normalized = str(token).strip()
        if normalized:
            return normalized
    return "source_attribution_receipt_missing"


async def _collect_narration_effect_audit_facts(
    *,
    workspace: Path,
    receipts: list[dict[str, Any]],
    cards_repo: _CardHistoryRepository,
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for receipt in receipts:
        tool = str(receipt.get("tool") or "").strip()
        if tool not in _NARRATION_EFFECT_TOOLS:
            continue
        execution_result = receipt.get("execution_result")
        if not isinstance(execution_result, dict) or not bool(execution_result.get("ok")):
            continue
        if tool == "write_file":
            entries.append(await _write_file_audit_entry(workspace=workspace, receipt=receipt))
            continue
        entries.append(await _status_update_audit_entry(cards_repo=cards_repo, receipt=receipt))
    if not entries:
        return {}
    verified_count = sum(1 for row in entries if row["audit_status"] == "verified")
    return {
        "audit_occurred": True,
        "verified_count": verified_count,
        "missing_effect_count": len(entries) - verified_count,
        "entries": entries,
    }


def _collect_idempotency_facts(*, receipts: list[dict[str, Any]]) -> dict[str, Any]:
    policy_rows = {
        str(row.get("surface") or "").strip(): dict(row)
        for row in idempotency_discipline_policy_snapshot().get("rows", [])
        if isinstance(row, dict)
    }
    operation_counts = Counter(
        str(receipt.get("operation_id") or "").strip()
        for receipt in receipts
        if str(receipt.get("operation_id") or "").strip()
    )
    surfaces: list[dict[str, Any]] = []
    for receipt in receipts:
        execution_result = receipt.get("execution_result")
        if not isinstance(execution_result, dict) or not bool(execution_result.get("ok")):
            continue
        operation_id = str(receipt.get("operation_id") or "").strip()
        if not operation_id:
            continue
        surface = _idempotency_surface_for_receipt(receipt)
        if not surface:
            continue
        policy = policy_rows.get(surface, {})
        target = _idempotency_target_for_receipt(receipt)
        row: dict[str, Any] = {
            "surface": surface,
            "operation_id": operation_id,
            "tool": str(receipt.get("tool") or "").strip(),
            "target": target,
            "dedupe_status": "reused" if operation_counts[operation_id] > 1 else "single_delivery",
            "conflict_action": str(policy.get("conflict_action") or "").strip(),
            "replay_allowed": bool(policy.get("replay_allowed", False)),
        }
        issue_id = str(receipt.get("_issue_id") or "").strip()
        if issue_id:
            row["issue_id"] = issue_id
        role_name = str(receipt.get("_role_name") or "").strip()
        if role_name:
            row["role_name"] = role_name
        turn_index = _normalize_turn_index(receipt.get("_turn_index"))
        if turn_index > 0:
            row["turn_index"] = turn_index
        _apply_control_plane_manifest_refs(entry=row, receipt=receipt)
        surfaces.append(row)
    if not surfaces:
        return {}
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in surfaces:
        deduped[(row["surface"], row["operation_id"])] = row
    entries = [deduped[key] for key in sorted(deduped)]
    return {
        "policy_schema_version": "1.0",
        "observed_surface_count": len(entries),
        "duplicate_operation_count": sum(1 for row in entries if row["dedupe_status"] == "reused"),
        "surfaces": entries,
    }


async def _write_file_audit_entry(*, workspace: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    execution_result = dict(receipt.get("execution_result") or {})
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    raw_path = str(execution_result.get("path") or tool_args.get("path") or "").strip()
    effect_target = _normalized_workspace_path(raw_path)
    entry = _base_audit_entry(receipt=receipt, effect_target=effect_target or raw_path, tool="write_file")
    if not raw_path:
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "artifact_path_missing"
        return entry
    observation = await observe_packet2_file(workspace=workspace, raw_path=raw_path)
    if observation == "outside":
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "artifact_path_outside_workspace"
        return entry
    if observation == "missing":
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "workspace_artifact_missing"
        return entry
    entry["audit_status"] = "verified"
    entry["failure_reason"] = "none"
    return entry


async def _status_update_audit_entry(
    *,
    cards_repo: _CardHistoryRepository,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    execution_result = dict(receipt.get("execution_result") or {})
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    issue_id = str(
        execution_result.get("issue_id") or tool_args.get("issue_id") or receipt.get("_issue_id") or ""
    ).strip()
    status = str(execution_result.get("status") or tool_args.get("status") or "").strip().lower()
    target = f"{issue_id}:{status}" if issue_id and status else issue_id or status
    entry = _base_audit_entry(receipt=receipt, effect_target=target, tool="update_issue_status")
    if not issue_id or not status:
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "card_status_target_missing"
        return entry
    history = await cards_repo.get_card_history(issue_id)
    marker = f"Set Status to '{status}'"
    if any(marker in str(row) for row in history):
        entry["audit_status"] = "verified"
        entry["failure_reason"] = "none"
        return entry
    entry["audit_status"] = "missing"
    entry["failure_reason"] = "card_status_transition_missing"
    return entry


def _base_audit_entry(*, receipt: dict[str, Any], effect_target: str, tool: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "operation_id": str(receipt.get("operation_id") or "").strip(),
        "tool": tool,
        "effect_target": str(effect_target or "").strip(),
    }
    issue_id = str(receipt.get("_issue_id") or "").strip()
    if issue_id:
        entry["issue_id"] = issue_id
    role_name = str(receipt.get("_role_name") or "").strip()
    if role_name:
        entry["role_name"] = role_name
    turn_index = _normalize_turn_index(receipt.get("_turn_index"))
    if turn_index > 0:
        entry["turn_index"] = turn_index
    step_id = str(receipt.get("step_id") or "").strip()
    if step_id:
        entry["step_id"] = step_id
    _apply_control_plane_manifest_refs(entry=entry, receipt=receipt)
    return entry


def _apply_control_plane_manifest_refs(*, entry: dict[str, Any], receipt: dict[str, Any]) -> None:
    manifest = (
        dict(receipt.get("tool_invocation_manifest") or {})
        if isinstance(receipt.get("tool_invocation_manifest"), dict)
        else {}
    )
    for field in (
        "control_plane_run_id",
        "control_plane_attempt_id",
        "control_plane_step_id",
    ):
        token = str(manifest.get(field) or "").strip()
        if token:
            entry[field] = token


def _source_receipt_provenance_entry(artifact_provenance_facts: dict[str, Any] | None) -> dict[str, Any] | None:
    facts = normalize_artifact_provenance_facts(artifact_provenance_facts)
    for entry in facts.get("artifacts", []):
        if str(entry.get("artifact_path") or "").strip() == SOURCE_ATTRIBUTION_RECEIPT_PATH:
            return dict(entry)
    return None


def _normalize_source_attribution_claims(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    claims: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        claim_id = str(item.get("claim_id") or "").strip()
        claim = str(item.get("claim") or "").strip()
        source_ids = sorted({str(token).strip() for token in item.get("source_ids", []) if str(token).strip()})
        if not claim_id or not claim or not source_ids:
            continue
        claims[claim_id] = {
            "claim_id": claim_id,
            "claim": claim,
            "source_ids": source_ids,
        }
    return [claims[key] for key in sorted(claims)]


def _normalize_source_attribution_sources(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    sources: dict[str, dict[str, Any]] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        source_id = str(item.get("source_id") or "").strip()
        title = str(item.get("title") or "").strip()
        uri = str(item.get("uri") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if not source_id or not title or not uri or not kind:
            continue
        sources[source_id] = {
            "source_id": source_id,
            "title": title,
            "uri": uri,
            "kind": kind,
        }
    return [sources[key] for key in sorted(sources)]


def _idempotency_surface_for_receipt(receipt: dict[str, Any]) -> str:
    tool = str(receipt.get("tool") or "").strip()
    if tool == "update_issue_status":
        return "status_update"
    if tool != "write_file":
        return ""
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    raw_path = str(tool_args.get("path") or "").strip()
    if _normalized_workspace_path(raw_path) == SOURCE_ATTRIBUTION_RECEIPT_PATH:
        return "source_attribution_receipt"
    return "artifact_write"


def _idempotency_target_for_receipt(receipt: dict[str, Any]) -> str:
    tool = str(receipt.get("tool") or "").strip()
    execution_result = dict(receipt.get("execution_result") or {})
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    if tool == "update_issue_status":
        issue_id = str(
            execution_result.get("issue_id") or tool_args.get("issue_id") or receipt.get("_issue_id") or ""
        ).strip()
        status = str(execution_result.get("status") or tool_args.get("status") or "").strip().lower()
        return f"{issue_id}:{status}" if issue_id and status else issue_id or status
    return _normalized_workspace_path(str(tool_args.get("path") or execution_result.get("path") or "").strip())


def _normalized_workspace_path(raw_path: str) -> str:
    candidate = Path(str(raw_path or "").strip())
    if not str(candidate):
        return ""
    parts = list(candidate.parts)
    if len(parts) >= 2 and parts[0].endswith(":"):
        parts = parts[1:]
    if "agent_output" in parts:
        start = parts.index("agent_output")
        return "/".join(parts[start:])
    return candidate.as_posix()
