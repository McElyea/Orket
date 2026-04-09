from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiofiles

from orket.naming import sanitize_name
from orket.runtime.run_start_artifacts import validate_run_identity_projection
from orket.runtime.run_summary_artifact_provenance import (
    ARTIFACT_PROVENANCE_KEY,
    build_artifact_provenance_extension,
    normalize_artifact_provenance_facts,
)
from orket.runtime.run_summary_control_plane import build_control_plane_summary_projection
from orket.runtime.run_summary_packet2 import (
    PACKET2_KEY,
    build_packet2_extension,
    normalize_packet2_facts,
)

_EXCLUDED_ARTIFACT_IDS = {"gitea_export", "run_summary", "run_summary_path"}
_PACKET1_SCHEMA_VERSION = "1.0"
_PACKET1_KEY = "truthful_runtime_packet1"
PACKET1_MISSING_TOKEN = "missing"
_PRIMARY_OUTPUT_KEYS = (
    "explicit_completion_output",
    "primary_work_artifact_output",
    "direct_response_output",
    "primary_artifact_output",
)
_CLASSIFICATION_RULE_ORDER = ("degraded", "repaired", "estimated", "inferred", "direct")
_EVIDENCE_SOURCE_BY_RULE = {
    "direct": "direct_execution",
    "inferred": "runtime_evidence",
    "estimated": "estimation_marker",
    "repaired": "validator_repair",
    "degraded": "fallback_or_reduced_capability",
}
_CONFORMANCE_REASON_ORDER = (
    "packet1_emission_failure",
    "classification_divergence",
    "silent_path_mismatch",
    "silent_repaired_success",
    "silent_degraded_success",
    "silent_unrecorded_fallback",
)
_DEFECT_ORDER = _CONFORMANCE_REASON_ORDER[1:]


def validate_run_summary_payload(payload: dict[str, Any]) -> None:
    run_id = str(payload.get("run_id") or "").strip()
    status = str(payload.get("status") or "").strip()
    duration_ms = payload.get("duration_ms")
    is_degraded = payload.get("is_degraded")
    failure_reason = payload.get("failure_reason")
    tools_used = payload.get("tools_used")
    artifact_ids = payload.get("artifact_ids")

    if not run_id:
        raise ValueError("run_summary_run_id_required")
    if not status:
        raise ValueError("run_summary_status_required")
    if duration_ms is not None and (not isinstance(duration_ms, int) or duration_ms < 0):
        raise ValueError("run_summary_duration_invalid")
    if is_degraded is not None and not isinstance(is_degraded, bool):
        raise ValueError("run_summary_is_degraded_invalid")
    if failure_reason is not None and not isinstance(failure_reason, str):
        raise ValueError("run_summary_failure_reason_invalid")
    _validate_token_list(tools_used, field_name="tools_used")
    _validate_token_list(artifact_ids, field_name="artifact_ids")
    packet1 = payload.get(_PACKET1_KEY)
    if packet1 is not None:
        _validate_projection_block(
            packet1,
            field_name="run_summary_truthful_runtime_packet1",
            expected_source="packet1_facts",
        )
    packet2 = payload.get(PACKET2_KEY)
    if packet2 is not None:
        _validate_projection_block(
            packet2,
            field_name="run_summary_truthful_runtime_packet2",
            expected_source="packet2_facts",
        )
    artifact_provenance = payload.get(ARTIFACT_PROVENANCE_KEY)
    if artifact_provenance is not None:
        _validate_projection_block(
            artifact_provenance,
            field_name="run_summary_truthful_runtime_artifact_provenance",
            expected_source="artifact_provenance_facts",
        )
    run_identity = payload.get("run_identity")
    if run_identity is not None:
        _validate_run_identity_for_run(
            run_identity,
            run_id=run_id,
            error_prefix="run_summary_run_identity",
        )
    control_plane = payload.get("control_plane")
    if control_plane is not None:
        _validate_projection_block(
            control_plane,
            field_name="run_summary_control_plane",
            expected_source="control_plane_records",
        )
        _validate_control_plane_projection_for_run(control_plane)


def build_run_summary_payload(
    *,
    run_id: str,
    status: str,
    failure_reason: str | None,
    started_at: str | None,
    ended_at: str | None,
    tool_names: list[str],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    duration_ms = _resolve_duration_ms(started_at=started_at, ended_at=ended_at)
    payload = {
        "run_id": str(run_id).strip(),
        "status": str(status).strip(),
        "duration_ms": duration_ms,
        "is_degraded": False,
        "tools_used": _normalize_token_list(tool_names),
        "artifact_ids": _artifact_ids(artifacts),
        "failure_reason": _normalize_failure_reason(failure_reason),
    }
    run_identity = artifacts.get("run_identity")
    if run_identity is not None:
        _validate_run_identity_for_run(
            run_identity,
            run_id=str(run_id).strip(),
            error_prefix="run_summary_run_identity",
        )
    packet1 = _build_packet1_extension(
        run_id=str(run_id).strip(),
        status=str(status).strip(),
        artifacts=artifacts,
        failure_reason=failure_reason,
    )
    if packet1 is not None:
        payload[_PACKET1_KEY] = packet1
    packet2 = build_packet2_extension(artifacts=artifacts)
    if packet2 is not None:
        payload[PACKET2_KEY] = packet2
    artifact_provenance = build_artifact_provenance_extension(artifacts=artifacts)
    if artifact_provenance is not None:
        payload[ARTIFACT_PROVENANCE_KEY] = artifact_provenance
    control_plane = build_control_plane_summary_projection(artifacts=artifacts)
    if control_plane is not None:
        payload["control_plane"] = control_plane
    cards_runtime = _build_cards_runtime_extension(artifacts=artifacts)
    if cards_runtime:
        payload["cards_runtime"] = cards_runtime
        execution_profile = str(cards_runtime.get("execution_profile") or "").strip()
        if execution_profile:
            payload["execution_profile"] = execution_profile
        stop_reason = str(cards_runtime.get("stop_reason") or "").strip()
        if stop_reason:
            payload["stop_reason"] = stop_reason
        if "odr_active" in cards_runtime:
            payload["odr_active"] = bool(cards_runtime.get("odr_active"))
        if str(cards_runtime.get("resolution_state") or "").strip():
            payload["cards_runtime_resolution_state"] = str(cards_runtime.get("resolution_state") or "").strip()
        for key in (
            "builder_seat_choice",
            "reviewer_seat_choice",
            "seat_coercion",
            "artifact_contract",
            "audit_mode",
            "odr_valid",
            "odr_pending_decisions",
            "odr_stop_reason",
            "odr_termination_reason",
            "odr_final_auditor_verdict",
            "odr_artifact_path",
            "last_valid_round_index",
            "last_emitted_round_index",
        ):
            if key in cards_runtime:
                payload[key] = cards_runtime[key]
    validate_run_summary_payload(payload)
    return payload


def build_degraded_run_summary_payload(
    *,
    run_id: str,
    status: str,
    failure_reason: str | None,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "run_id": str(run_id).strip(),
        "status": str(status).strip(),
        "duration_ms": None,
        "is_degraded": True,
        "tools_used": [],
        "artifact_ids": _artifact_ids(artifacts),
        "failure_reason": _normalize_failure_reason(failure_reason),
    }
    validate_run_summary_payload(payload)
    return payload


async def generate_run_summary_for_finalize(
    *,
    workspace: Path,
    run_id: str,
    status: str,
    failure_reason: str | None,
    started_at: str | None,
    ended_at: str | None,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    tool_names = await _tool_names_from_receipts(workspace=workspace, run_id=run_id)
    return build_run_summary_payload(
        run_id=run_id,
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        ended_at=ended_at,
        tool_names=tool_names,
        artifacts=artifacts,
    )


def reconstruct_run_summary(
    events: list[dict[str, Any]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    ordered_events = sorted(
        [dict(event or {}) for event in events if isinstance(event, dict)],
        key=lambda event: (
            int(event.get("event_seq") or event.get("sequence_number") or 0),
            str(event.get("kind") or ""),
        ),
    )
    run_id = str(session_id or "").strip()
    artifacts: dict[str, Any] = {}
    tool_names: list[str] = []
    started_at: str | None = None
    ended_at: str | None = None
    status = ""
    failure_reason: str | None = None
    packet1_event_facts: dict[str, Any] = {}
    packet2_event_facts: dict[str, Any] = {}
    artifact_provenance_event_facts: dict[str, Any] = {}

    for event in ordered_events:
        kind = str(event.get("kind") or "").strip()
        if not run_id:
            run_id = str(event.get("run_id") or event.get("session_id") or "").strip()
        event_artifacts = event.get("artifacts")
        if isinstance(event_artifacts, dict):
            artifacts.update(dict(event_artifacts))
        run_identity = artifacts.get("run_identity")
        if run_identity is not None and not started_at:
            started_at = validate_run_identity_projection(
                run_identity,
                error_prefix="run_summary_run_identity",
            )["start_time"]
        if kind == "run_started" and not started_at:
            started_at = str(event.get("timestamp") or "").strip() or None
            continue
        if kind == "tool_call":
            tool_name = str(event.get("tool_name") or event.get("tool") or "").strip()
            if tool_name:
                tool_names.append(tool_name)
            continue
        if kind == "packet1_fact":
            packet1_event_facts.update(_normalize_packet1_facts(event.get("packet1_facts")))
            continue
        if kind == "packet2_fact":
            packet2_event_facts.update(normalize_packet2_facts(event.get("packet2_facts")))
            continue
        if kind == "artifact_provenance_fact":
            artifact_provenance_event_facts.update(
                normalize_artifact_provenance_facts(event.get("artifact_provenance_facts"))
            )
            continue
        if kind != "run_finalized":
            continue
        status = str(event.get("status") or status).strip()
        normalized_failure_reason = _normalize_failure_reason(event.get("failure_reason"))
        if normalized_failure_reason is not None:
            failure_reason = normalized_failure_reason
        ended_at = str(event.get("timestamp") or "").strip() or ended_at

    if not run_id:
        raise ValueError("run_summary_run_id_required")
    if not status:
        raise ValueError("run_summary_status_required")
    if packet1_event_facts:
        artifacts["packet1_facts"] = {
            **_normalize_packet1_facts(artifacts.get("packet1_facts")),
            **packet1_event_facts,
        }
    if packet2_event_facts:
        artifacts["packet2_facts"] = {
            **normalize_packet2_facts(artifacts.get("packet2_facts")),
            **packet2_event_facts,
        }
    if artifact_provenance_event_facts:
        artifacts["artifact_provenance_facts"] = {
            **normalize_artifact_provenance_facts(artifacts.get("artifact_provenance_facts")),
            **artifact_provenance_event_facts,
        }
    return build_run_summary_payload(
        run_id=run_id,
        status=status,
        failure_reason=failure_reason,
        started_at=started_at,
        ended_at=ended_at,
        tool_names=tool_names,
        artifacts=artifacts,
    )


async def write_run_summary_artifact(
    *,
    root: Path,
    session_id: str,
    payload: dict[str, Any],
) -> Path:
    validate_run_summary_payload(payload)
    run_summary_path = Path(root) / "runs" / str(session_id).strip() / "run_summary.json"
    await asyncio.to_thread(run_summary_path.parent.mkdir, parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    async with aiofiles.open(run_summary_path, mode="w", encoding="utf-8") as handle:
        await handle.write(content)
    return run_summary_path


async def _tool_names_from_receipts(*, workspace: Path, run_id: str) -> list[str]:
    receipt_paths = await asyncio.to_thread(_receipt_paths, Path(workspace), str(run_id))
    tool_names: list[str] = []
    for path in receipt_paths:
        async with aiofiles.open(path, encoding="utf-8") as handle:
            async for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    continue
                tool_name = str(payload.get("tool") or payload.get("tool_name") or "").strip()
                if tool_name:
                    tool_names.append(tool_name)
    return _normalize_token_list(tool_names)


def _receipt_paths(workspace: Path, run_id: str) -> list[Path]:
    session_root = workspace / "observability" / sanitize_name(run_id)
    if not session_root.exists():
        return []
    paths: list[Path] = []
    for issue_dir in sorted(session_root.iterdir(), key=lambda path: path.name):
        if not issue_dir.is_dir():
            continue
        for turn_dir in sorted(issue_dir.iterdir(), key=lambda path: path.name):
            if not turn_dir.is_dir():
                continue
            candidate = turn_dir / "protocol_receipts.log"
            if candidate.exists():
                paths.append(candidate)
    return paths


def _artifact_ids(artifacts: dict[str, Any]) -> list[str]:
    rows = []
    for artifact_id in sorted(artifacts.keys()):
        normalized_id = str(artifact_id or "").strip()
        if not normalized_id or normalized_id in _EXCLUDED_ARTIFACT_IDS:
            continue
        artifact_value = artifacts.get(artifact_id)
        if not isinstance(artifact_value, (dict, list)):
            continue
        rows.append(normalized_id)
    return rows


def _resolve_duration_ms(*, started_at: str | None, ended_at: str | None) -> int:
    normalized_start = str(started_at or "").strip()
    normalized_end = str(ended_at or "").strip()
    if not normalized_start or not normalized_end:
        raise ValueError("run_summary_duration_missing")
    start_dt = datetime.fromisoformat(normalized_start)
    end_dt = datetime.fromisoformat(normalized_end)
    delta_ms = int((end_dt - start_dt).total_seconds() * 1000)
    if delta_ms < 0:
        raise ValueError("run_summary_duration_negative")
    return delta_ms


def _normalize_failure_reason(value: Any) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def _normalize_token_list(values: list[str]) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for raw in values:
        token = str(raw or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        rows.append(token)
    rows.sort()
    return rows


def _validate_token_list(value: Any, *, field_name: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"run_summary_{field_name}_invalid")
    normalized = _normalize_token_list([str(item) for item in value])
    if normalized != value:
        raise ValueError(f"run_summary_{field_name}_not_canonical")


def _validate_projection_block(value: Any, *, field_name: str, expected_source: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name}_invalid")
    if str(value.get("projection_source") or "").strip() != expected_source:
        raise ValueError(f"{field_name}_projection_source_invalid")
    if value.get("projection_only") is not True:
        raise ValueError(f"{field_name}_projection_only_invalid")


def _validate_run_identity_for_run(
    value: Any,
    *,
    run_id: str,
    error_prefix: str,
) -> dict[str, Any]:
    normalized_run_identity = validate_run_identity_projection(
        value,
        error_prefix=error_prefix,
    )
    if normalized_run_identity["run_id"] != run_id:
        raise ValueError("run_summary_run_identity_run_id_mismatch")
    return normalized_run_identity


def _validate_control_plane_projection_for_run(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("run_summary_control_plane_invalid")
    normalized_control_plane = dict(value)
    projected_run_id = str(normalized_control_plane.get("run_id") or "").strip()
    current_attempt_id = str(normalized_control_plane.get("current_attempt_id") or "").strip()
    projected_attempt_id = str(normalized_control_plane.get("attempt_id") or "").strip()
    projected_step_id = str(normalized_control_plane.get("step_id") or "").strip()
    projected_attempt_state = str(normalized_control_plane.get("attempt_state") or "").strip()
    projected_step_kind = str(normalized_control_plane.get("step_kind") or "").strip()
    projected_attempt_ordinal = normalized_control_plane.get("attempt_ordinal")
    if (current_attempt_id or projected_attempt_id or projected_step_id) and not projected_run_id:
        raise ValueError("run_summary_control_plane_run_id_required")
    if current_attempt_id and not projected_attempt_id:
        raise ValueError("run_summary_control_plane_attempt_id_required")
    if projected_step_id and not projected_attempt_id:
        raise ValueError("run_summary_control_plane_attempt_id_required")
    if (projected_attempt_state or projected_attempt_ordinal not in (None, "")) and not projected_attempt_id:
        raise ValueError("run_summary_control_plane_attempt_id_required")
    if projected_step_kind and not projected_step_id:
        raise ValueError("run_summary_control_plane_step_id_required")
    if projected_run_id:
        for field_name in (
            "run_state",
            "workload_id",
            "workload_version",
            "policy_snapshot_id",
            "configuration_snapshot_id",
        ):
            if not str(normalized_control_plane.get(field_name) or "").strip():
                raise ValueError(f"run_summary_control_plane_{field_name}_required")
        attempt_prefix = f"{projected_run_id}:attempt:"
        step_prefix = f"{projected_run_id}:step:"
        if current_attempt_id and not current_attempt_id.startswith(attempt_prefix):
            raise ValueError("run_summary_control_plane_current_attempt_id_run_lineage_mismatch")
        if projected_attempt_id and not projected_attempt_id.startswith(attempt_prefix):
            raise ValueError("run_summary_control_plane_attempt_id_run_lineage_mismatch")
        if projected_step_id and not projected_step_id.startswith(step_prefix):
            raise ValueError("run_summary_control_plane_step_id_run_lineage_mismatch")
    if projected_attempt_id:
        if not projected_attempt_state:
            raise ValueError("run_summary_control_plane_attempt_state_required")
        if projected_attempt_ordinal is None:
            raise ValueError("run_summary_control_plane_attempt_ordinal_required")
        try:
            attempt_ordinal = int(projected_attempt_ordinal)
        except (TypeError, ValueError):
            raise ValueError("run_summary_control_plane_attempt_ordinal_required") from None
        if attempt_ordinal <= 0:
            raise ValueError("run_summary_control_plane_attempt_ordinal_required")
    if projected_step_id and not projected_step_kind:
        raise ValueError("run_summary_control_plane_step_kind_required")
    if current_attempt_id and projected_attempt_id and current_attempt_id != projected_attempt_id:
        raise ValueError("run_summary_control_plane_current_attempt_id_mismatch")
    return normalized_control_plane


def _build_packet1_extension(
    *,
    run_id: str,
    status: str,
    artifacts: dict[str, Any],
    failure_reason: str | None,
) -> dict[str, Any] | None:
    facts = _collect_packet1_facts(artifacts)
    if not facts:
        return None

    selection = _select_primary_output(facts)
    primary_kind = str(selection.get("kind") or "none")
    primary_id = str(selection.get("id") or "").strip()
    classification_applicable = primary_kind != "none"
    raw_primary_output_facts = facts.get("primary_output_facts")
    primary_output_facts: dict[str, Any] = (
        {str(key): value for key, value in raw_primary_output_facts.items()}
        if isinstance(raw_primary_output_facts, dict)
        else facts
    )
    raw_run_surface_facts = facts.get("run_surface_facts")
    run_surface_facts: dict[str, Any] = (
        {str(key): value for key, value in raw_run_surface_facts.items()}
        if isinstance(raw_run_surface_facts, dict)
        else facts
    )
    primary_eval = _evaluate_classification(
        primary_output_facts
    )
    run_eval = _evaluate_classification(
        run_surface_facts
    )
    defects = _detect_packet1_defects(
        facts=facts,
        status=status,
        classification_applicable=classification_applicable,
        primary_eval=primary_eval,
        run_eval=run_eval,
    )
    conformance_reasons = list(defects)
    conformance_status = "non_conformant" if conformance_reasons else "conformant"

    provenance = {
        "run_id": run_id,
        "terminal_status": status,
        "primary_output_kind": primary_kind,
        "intended_provider": _resolve_packet1_token(facts.get("intended_provider"), "ollama"),
        "intended_model": _resolve_packet1_token(facts.get("intended_model")),
        "intended_profile": _resolve_packet1_token(facts.get("intended_profile")),
        "actual_provider": _resolve_packet1_token(
            facts.get("actual_provider"), facts.get("intended_provider"), "ollama"
        ),
        "actual_model": _resolve_packet1_token(facts.get("actual_model"), facts.get("intended_model")),
        "actual_profile": _resolve_packet1_token(facts.get("actual_profile"), facts.get("intended_profile")),
        "path_mismatch": bool(facts.get("path_mismatch", False)),
        "mismatch_reason": str(facts.get("mismatch_reason") or "none"),
        "retry_occurred": bool(facts.get("retry_occurred", False)),
        "repair_occurred": bool(facts.get("repair_occurred", False)),
        "fallback_occurred": bool(facts.get("fallback_occurred", False)),
        "execution_profile": _resolve_execution_profile(facts),
    }
    if primary_id:
        provenance["primary_output_id"] = primary_id
    if isinstance(selection, dict):
        for field in (
            "control_plane_run_id",
            "control_plane_attempt_id",
            "control_plane_step_id",
        ):
            token = str(selection.get(field) or "").strip()
            if token:
                provenance[field] = token

    classification: dict[str, Any] = {"classification_applicable": classification_applicable}
    if classification_applicable:
        classification["truth_classification"] = str(primary_eval["rule"])
        classification["classification_basis"] = {
            "rule": str(primary_eval["rule"]),
            "evidence_source": str(primary_eval["evidence_source"]),
        }
        provenance["truth_classification"] = str(primary_eval["rule"])

    return {
        "schema_version": _PACKET1_SCHEMA_VERSION,
        "projection_source": "packet1_facts",
        "projection_only": True,
        "provenance": provenance,
        "classification": classification,
        "defects": {
            "defects_present": bool(defects),
            "defect_families": defects,
        },
        "packet1_conformance": {
            "status": conformance_status,
            "reasons": conformance_reasons,
        },
    }


def _collect_packet1_facts(artifacts: dict[str, Any]) -> dict[str, Any]:
    packet1_facts = _normalize_packet1_facts(artifacts.get("packet1_facts"))
    if "intended_provider" not in packet1_facts:
        packet1_facts["intended_provider"] = "ollama"
    if "actual_provider" not in packet1_facts:
        packet1_facts["actual_provider"] = packet1_facts.get("intended_provider")
    return packet1_facts


def _build_cards_runtime_extension(*, artifacts: dict[str, Any]) -> dict[str, Any]:
    value = artifacts.get("cards_runtime_facts")
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): item for key, item in value.items() if str(key).strip()}


def _normalize_packet1_facts(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key).strip(): item for key, item in value.items() if str(key).strip()}


def _resolve_packet1_token(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        raw = str(value).strip()
        if not raw:
            continue
        if raw.lower() in {"none", "unknown"}:
            continue
        return raw
    return PACKET1_MISSING_TOKEN


def _select_primary_output(facts: dict[str, Any]) -> dict[str, str]:
    for key in _PRIMARY_OUTPUT_KEYS:
        candidate = facts.get(key)
        if not isinstance(candidate, dict):
            continue
        candidate_id = str(candidate.get("id") or "").strip()
        candidate_kind = str(candidate.get("kind") or "").strip()
        if candidate_kind in {"response", "artifact"}:
            selected = {"kind": candidate_kind, "id": candidate_id}
            for field in (
                "control_plane_run_id",
                "control_plane_attempt_id",
                "control_plane_step_id",
            ):
                token = str(candidate.get(field) or "").strip()
                if token:
                    selected[field] = token
            return selected
    return {"kind": "none", "id": ""}


def _evaluate_classification(facts: dict[str, Any]) -> dict[str, str]:
    for rule in _CLASSIFICATION_RULE_ORDER:
        if _rule_matches(rule, facts):
            return {
                "rule": rule,
                "evidence_source": _EVIDENCE_SOURCE_BY_RULE[rule],
            }
    return {
        "rule": "direct",
        "evidence_source": _EVIDENCE_SOURCE_BY_RULE["direct"],
    }


def _rule_matches(rule: str, facts: dict[str, Any]) -> bool:
    if rule == "degraded":
        return bool(facts.get("fallback_occurred")) or _resolve_execution_profile(facts) != "normal"
    if rule == "repaired":
        return bool(facts.get("repair_occurred")) and bool(facts.get("repair_material_change", True))
    if rule == "estimated":
        return bool(facts.get("estimated_output"))
    if rule == "inferred":
        return bool(facts.get("inferred_output"))
    return True


def _resolve_execution_profile(facts: dict[str, Any]) -> str:
    explicit = str(facts.get("execution_profile") or "").strip()
    if explicit in {"normal", "fallback", "reduced_capability"}:
        return explicit
    if bool(facts.get("fallback_occurred")):
        return "fallback"
    if bool(facts.get("reduced_capability")):
        return "reduced_capability"
    return "normal"


def _detect_packet1_defects(
    *,
    facts: dict[str, Any],
    status: str,
    classification_applicable: bool,
    primary_eval: dict[str, str],
    run_eval: dict[str, str],
) -> list[str]:
    defects: list[str] = []
    status_token = str(status or "").strip().lower()
    success_like = status_token in {"done", "success", "succeeded", "incomplete"}
    machine_mismatch_indicator = bool(facts.get("machine_mismatch_indicator", False))
    if bool(facts.get("path_mismatch")) and not machine_mismatch_indicator:
        defects.append("silent_path_mismatch")
    if (
        bool(facts.get("repair_occurred"))
        and success_like
        and bool(facts.get("output_presented_as_normal_success", True))
    ):
        defects.append("silent_repaired_success")
    if (
        success_like
        and bool(facts.get("output_presented_as_normal_success", True))
        and (_resolve_execution_profile(facts) == "reduced_capability" or bool(facts.get("fallback_occurred")))
    ):
        defects.append("silent_degraded_success")
    if bool(facts.get("fallback_path_detected")) and not bool(facts.get("fallback_occurred")):
        defects.append("silent_unrecorded_fallback")
    if classification_applicable and str(primary_eval.get("rule") or "") != str(run_eval.get("rule") or ""):
        defects.append("classification_divergence")
    return [token for token in _DEFECT_ORDER if token in defects]
