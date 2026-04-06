from __future__ import annotations

import asyncio
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Protocol

import aiofiles

from orket.naming import sanitize_name
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
    receipts = await _load_protocol_receipts(workspace=workspace, run_id=run_id)
    normalized_policy = normalize_truthful_runtime_policy(policy)
    narration_facts = await _collect_narration_effect_audit_facts(
        workspace=workspace,
        receipts=receipts,
        cards_repo=cards_repo,
    )
    source_attribution_facts = await collect_source_attribution_facts(
        workspace=workspace,
        policy=normalized_policy,
        artifact_provenance_facts=artifact_provenance_facts,
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
    should_emit = bool(normalized_policy.get("configured")) or receipt_path.exists() or provenance_entry is not None
    if not should_emit:
        return {}

    missing_requirements: list[str] = []
    claims: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    if not receipt_path.exists():
        missing_requirements.append("source_attribution_receipt_missing")
    else:
        try:
            async with aiofiles.open(receipt_path, encoding="utf-8") as handle:
                payload = json.loads(await handle.read())
        except (OSError, ValueError, TypeError):
            payload = None
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
            entries.append(_write_file_audit_entry(workspace=workspace, receipt=receipt))
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


async def _load_protocol_receipts(*, workspace: Path, run_id: str) -> list[dict[str, Any]]:
    receipts: list[dict[str, Any]] = []
    observability_root = Path(workspace) / "observability" / sanitize_name(run_id)
    if not observability_root.exists():
        return receipts
    protocol_turn_dirs: set[Path] = set()
    for receipt_path in sorted(observability_root.rglob("protocol_receipts.log")):
        protocol_turn_dirs.add(receipt_path.parent.resolve())
        issue_id, role_name, turn_index = _receipt_context(
            receipt_path=receipt_path, run_id=run_id, workspace=workspace
        )
        try:
            async with aiofiles.open(receipt_path, encoding="utf-8") as handle:
                async for line in handle:
                    if not line.strip():
                        continue
                    try:
                        payload = json.loads(line)
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(payload, dict):
                        continue
                    receipts.append(
                        {
                            **payload,
                            "_issue_id": issue_id,
                            "_role_name": role_name,
                            "_turn_index": turn_index,
                        }
                    )
        except OSError:
            continue
    legacy_turn_dirs = await _legacy_turn_dirs(
        observability_root=observability_root,
        protocol_turn_dirs=protocol_turn_dirs,
    )
    for turn_dir in legacy_turn_dirs:
        receipts.extend(await _load_legacy_turn_receipts(turn_dir=turn_dir, run_id=run_id, workspace=workspace))
    return sorted(
        receipts,
        key=lambda row: (
            str(row.get("_issue_id") or ""),
            _normalize_turn_index(row.get("_turn_index")),
            int(row.get("receipt_seq") or row.get("tool_index") or 0),
            str(row.get("operation_id") or ""),
        ),
    )


async def _legacy_turn_dirs(*, observability_root: Path, protocol_turn_dirs: set[Path]) -> list[Path]:
    def _collect() -> list[Path]:
        turn_dirs: list[Path] = []
        for issue_dir in sorted(observability_root.iterdir(), key=lambda path: path.name):
            if not issue_dir.is_dir():
                continue
            for turn_dir in sorted(issue_dir.iterdir(), key=lambda path: path.name):
                if not turn_dir.is_dir():
                    continue
                if (turn_dir.resolve() in protocol_turn_dirs) or ("_" not in turn_dir.name):
                    continue
                if (turn_dir / "parsed_tool_calls.json").exists():
                    turn_dirs.append(turn_dir)
        return turn_dirs

    return await asyncio.to_thread(_collect)


async def _load_legacy_turn_receipts(*, turn_dir: Path, run_id: str, workspace: Path) -> list[dict[str, Any]]:
    issue_id, role_name, turn_index = _turn_context(turn_dir=turn_dir, run_id=run_id, workspace=workspace)
    if not issue_id or turn_index <= 0:
        return []
    parsed_tool_calls = await _load_json_payload(turn_dir / "parsed_tool_calls.json")
    if not isinstance(parsed_tool_calls, list):
        return []
    receipts: list[dict[str, Any]] = []
    for tool_index, item in enumerate(parsed_tool_calls):
        if not isinstance(item, dict):
            continue
        tool_name = str(item.get("tool") or "").strip()
        if not tool_name:
            continue
        tool_args = dict(item.get("args") or {}) if isinstance(item.get("args"), dict) else {}
        result_path = (
            turn_dir / f"tool_result_{sanitize_name(tool_name)}_{_legacy_tool_replay_key(tool_name, tool_args)}.json"
        )
        execution_result = await _load_json_payload(result_path)
        if not isinstance(execution_result, dict):
            continue
        receipts.append(
            {
                "run_id": str(run_id),
                "step_id": f"{issue_id}:{turn_index}",
                "receipt_seq": tool_index + 1,
                "operation_id": _legacy_operation_id(
                    issue_id=issue_id,
                    role_name=role_name,
                    turn_index=turn_index,
                    tool_index=tool_index,
                    tool_name=tool_name,
                    tool_args=tool_args,
                ),
                "tool_index": tool_index,
                "tool": tool_name,
                "tool_args": tool_args,
                "execution_result": execution_result,
                "_issue_id": issue_id,
                "_role_name": role_name,
                "_turn_index": turn_index,
            }
        )
    return receipts


async def _load_json_payload(path: Path) -> Any:
    try:
        async with aiofiles.open(path, encoding="utf-8") as handle:
            return json.loads(await handle.read())
    except (OSError, TypeError, ValueError):
        return None


def _turn_context(*, turn_dir: Path, run_id: str, workspace: Path) -> tuple[str, str, int]:
    return _receipt_context(receipt_path=turn_dir / "protocol_receipts.log", run_id=run_id, workspace=workspace)


def _legacy_tool_replay_key(tool_name: str, tool_args: dict[str, Any]) -> str:
    payload = {
        "v": 1,
        "kind": "tool_replay_key",
        "fields": [str(tool_name or ""), dict(tool_args or {})],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _legacy_operation_id(
    *,
    issue_id: str,
    role_name: str,
    turn_index: int,
    tool_index: int,
    tool_name: str,
    tool_args: dict[str, Any],
) -> str:
    return (
        "legacy:"
        f"{sanitize_name(issue_id)}:"
        f"{sanitize_name(role_name)}:"
        f"{turn_index:03d}:"
        f"{tool_index:03d}:"
        f"{sanitize_name(tool_name)}:"
        f"{_legacy_tool_replay_key(tool_name, tool_args)}"
    )


def _receipt_context(*, receipt_path: Path, run_id: str, workspace: Path) -> tuple[str, str, int]:
    session_root = Path(workspace) / "observability" / sanitize_name(run_id)
    try:
        relative_path = receipt_path.relative_to(session_root)
    except ValueError:
        return "", "", 0
    parts = relative_path.parts
    if len(parts) < 3:
        return "", "", 0
    issue_id = str(parts[0]).strip()
    role_token = str(parts[1]).strip()
    turn_index = 0
    role_name = ""
    if "_" in role_token:
        raw_turn_index, role_name = role_token.split("_", 1)
        turn_index = _normalize_turn_index(raw_turn_index)
    return issue_id, role_name.strip(), turn_index


def _write_file_audit_entry(*, workspace: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    execution_result = dict(receipt.get("execution_result") or {})
    tool_args = dict(receipt.get("tool_args") or {}) if isinstance(receipt.get("tool_args"), dict) else {}
    raw_path = str(execution_result.get("path") or tool_args.get("path") or "").strip()
    effect_target = _normalized_workspace_path(raw_path)
    entry = _base_audit_entry(receipt=receipt, effect_target=effect_target or raw_path, tool="write_file")
    if not raw_path:
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "artifact_path_missing"
        return entry
    resolved = _resolve_workspace_candidate(workspace=workspace, raw_path=raw_path)
    if resolved is None:
        entry["audit_status"] = "missing"
        entry["failure_reason"] = "artifact_path_outside_workspace"
        return entry
    if not resolved.exists() or not resolved.is_file():
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


def _resolve_workspace_candidate(*, workspace: Path, raw_path: str) -> Path | None:
    candidate = Path(raw_path)
    workspace_root = Path(workspace).resolve()
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(workspace_root):
        return None
    return resolved


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


def _normalize_turn_index(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return max(0, value)
    raw = str(value or "").strip()
    if not raw:
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        return 0
