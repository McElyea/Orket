from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.kernel.v1.odr.live_runner import run_live_refinement
from orket.logging import log_event

_SUCCESS_STOP_REASONS = {"STABLE_DIFF_FLOOR", "LOOP_DETECTED"}
_MAX_ROUNDS_STOP_REASON = "MAX_ROUNDS"


def _coerce_int(value: object) -> int | None:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _normalize_model_identity(value: object) -> str:
    return str(value or "").strip().lower()


def _resolve_audit_mode(*, selected_model: str, auditor_model: str) -> str:
    if (
        _normalize_model_identity(selected_model)
        and _normalize_model_identity(auditor_model)
        and _normalize_model_identity(selected_model) != _normalize_model_identity(auditor_model)
    ):
        return "independent"
    return "self_audit_fallback"


def _build_odr_task(*, issue: Any, cards_runtime: dict[str, Any]) -> str:
    artifact_contract = dict(cards_runtime.get("artifact_contract") or {})
    required_write_paths = list(artifact_contract.get("required_write_paths") or [])
    required_read_paths = list(artifact_contract.get("required_read_paths") or [])
    lines = [
        f"Cards issue id: {getattr(issue, 'id', '')}",
        f"Issue summary: {getattr(issue, 'name', '')}",
        f"Artifact kind: {artifact_contract.get('kind', '')}",
        f"Primary output: {artifact_contract.get('primary_output', '')}",
    ]
    if required_write_paths:
        lines.append(f"Required write paths: {', '.join(required_write_paths)}")
    if required_read_paths:
        lines.append(f"Required read paths: {', '.join(required_read_paths)}")
    note = str(getattr(issue, "note", "") or "").strip()
    if note:
        lines.append(f"Operator note: {note}")
    return "\n".join(lines)


def _cached_result(issue: Any, *, run_id: str) -> dict[str, Any] | None:
    params = getattr(issue, "params", None)
    if not isinstance(params, dict):
        return None
    cached = params.get("odr_result")
    if isinstance(cached, dict) and str(cached.get("odr_run_id") or "").strip() == str(run_id).strip():
        return dict(cached)
    return None


def _resolve_odr_max_rounds(issue: Any, *, default: int) -> int:
    params = getattr(issue, "params", None)
    if not isinstance(params, dict):
        return int(default)
    raw_nested = params.get("cards_runtime")
    nested = raw_nested if isinstance(raw_nested, dict) else {}
    raw = nested.get("odr_max_rounds") if "odr_max_rounds" in nested else params.get("odr_max_rounds")
    parsed = _coerce_int(raw)
    if parsed is None:
        return int(default)
    return max(0, parsed)


def _odr_max_rounds_accepted(issue: Any) -> bool:
    params = getattr(issue, "params", None)
    if not isinstance(params, dict):
        return False
    raw_nested = params.get("cards_runtime")
    nested = raw_nested if isinstance(raw_nested, dict) else {}
    raw = (
        nested.get("odr_max_rounds_accepted")
        if "odr_max_rounds_accepted" in nested
        else params.get("odr_max_rounds_accepted")
    )
    return bool(raw)


def _odr_prebuild_accepted(
    *,
    stop_reason: str,
    odr_valid: bool,
    pending_decisions: int,
    max_rounds_accepted: bool = False,
) -> bool:
    if not bool(odr_valid):
        return False
    if int(pending_decisions) > 0:
        return False
    normalized_stop_reason = str(stop_reason or "").strip()
    if normalized_stop_reason in _SUCCESS_STOP_REASONS:
        return True
    return normalized_stop_reason == _MAX_ROUNDS_STOP_REASON and bool(max_rounds_accepted)


async def _skip_odr_prebuild(
    *,
    workspace: Path,
    issue: Any,
    run_id: str,
    selected_model: str,
    cards_runtime: dict[str, Any],
    async_cards: Any,
) -> dict[str, Any]:
    summary = {
        "odr_run_id": str(run_id),
        "odr_valid": True,
        "odr_pending_decisions": 0,
        "odr_stop_reason": "SKIPPED",
        "odr_termination_reason": "operator_disabled",
        "odr_final_auditor_verdict": None,
        "odr_artifact_path": None,
        "odr_requirement": "",
        "odr_rounds_completed": 0,
        "odr_max_rounds": 0,
        "odr_accepted": True,
        "odr_active": False,
    }
    params = getattr(issue, "params", None)
    issue.params = dict(params or {}) if isinstance(params, dict) else {}
    issue.params["odr_result"] = dict(summary)
    await async_cards.save(issue.model_dump(by_alias=True))
    log_event(
        "odr_prebuild_skipped",
        {
            "session_id": str(run_id),
            "issue_id": str(getattr(issue, "id", "")),
            "execution_profile": str(cards_runtime.get("execution_profile") or ""),
            "selected_model": str(selected_model),
            **dict(summary),
        },
        workspace,
        level="info",
    )
    return summary


async def run_cards_odr_prebuild(
    *,
    workspace: Path,
    issue: Any,
    run_id: str,
    selected_model: str,
    cards_runtime: dict[str, Any],
    model_client: Any,
    auditor_client: Any | None = None,
    async_cards: Any,
    max_rounds: int = 8,
) -> dict[str, Any]:
    cached = _cached_result(issue, run_id=run_id)
    if cached is not None:
        return cached

    task = _build_odr_task(issue=issue, cards_runtime=cards_runtime)
    effective_max_rounds = _resolve_odr_max_rounds(issue, default=max_rounds)
    if effective_max_rounds == 0:
        return await _skip_odr_prebuild(
            workspace=workspace,
            issue=issue,
            run_id=run_id,
            selected_model=selected_model,
            cards_runtime=cards_runtime,
            async_cards=async_cards,
        )
    result = await run_live_refinement(
        task=task,
        architect_client=model_client,
        auditor_client=auditor_client if auditor_client is not None else model_client,
        max_rounds=effective_max_rounds,
    )
    if str(result.get("odr_failure_mode") or "") == "format_violation" and effective_max_rounds > 1:
        log_event(
            "odr_prebuild_format_violation_retry",
            {
                "session_id": str(run_id),
                "issue_id": str(getattr(issue, "id", "")),
                "original_stop_reason": str(result.get("odr_stop_reason") or ""),
            },
            workspace,
        )
        retry_result = await run_live_refinement(
            task=task,
            architect_client=model_client,
            auditor_client=auditor_client if auditor_client is not None else model_client,
            max_rounds=1,
        )
        if str(retry_result.get("odr_failure_mode") or "") != "format_violation":
            result = retry_result

    stop_reason = str(result.get("odr_stop_reason") or "")
    odr_valid = bool(result.get("odr_valid"))
    pending_decisions = int(result.get("odr_pending_decisions") or 0)
    accepted = _odr_prebuild_accepted(
        stop_reason=stop_reason,
        odr_valid=odr_valid,
        pending_decisions=pending_decisions,
        max_rounds_accepted=_odr_max_rounds_accepted(issue),
    )
    artifact_path = f"observability/{str(run_id).strip()}/{str(getattr(issue, 'id', '')).strip()}/odr_refinement.json"
    auditor_model = str(
        getattr(auditor_client, "model", "")
        or getattr(getattr(auditor_client, "provider", None), "model", "")
        or selected_model
    )
    artifact_payload = {
        "schema_version": "cards.odr.prebuild.v1",
        "run_id": str(run_id),
        "issue_id": str(getattr(issue, "id", "")),
        "selected_model": str(selected_model),
        "auditor_model": auditor_model,
        "audit_mode": _resolve_audit_mode(selected_model=selected_model, auditor_model=auditor_model),
        "execution_profile": str(cards_runtime.get("execution_profile") or ""),
        "odr_active": True,
        "task": task,
        "accepted": accepted,
        **dict(result),
    }
    await AsyncFileTools(workspace).write_file(
        artifact_path,
        json.dumps(artifact_payload, indent=2, ensure_ascii=True),
    )

    summary = {
        "odr_run_id": str(run_id),
        "odr_valid": odr_valid,
        "odr_pending_decisions": pending_decisions,
        "odr_stop_reason": stop_reason or None,
        "odr_termination_reason": str(result.get("termination_reason") or "").strip() or None,
        "odr_final_auditor_verdict": str(result.get("final_auditor_verdict") or "").strip() or None,
        "odr_artifact_path": artifact_path,
        "odr_requirement": str(result.get("final_requirement") or "").strip(),
        "odr_rounds_completed": int(result.get("rounds_completed") or 0),
        "audit_mode": _resolve_audit_mode(selected_model=selected_model, auditor_model=auditor_model),
        "last_valid_round_index": int(result.get("last_valid_round_index") or 0),
        "last_emitted_round_index": int(result.get("last_emitted_round_index") or 0),
        "odr_max_rounds": effective_max_rounds,
        "odr_max_rounds_accepted": _odr_max_rounds_accepted(issue),
        "odr_accepted": accepted,
    }
    params = getattr(issue, "params", None)
    issue.params = dict(params or {}) if isinstance(params, dict) else {}
    issue.params["odr_result"] = dict(summary)
    await async_cards.save(issue.model_dump(by_alias=True))

    event_name = "odr_prebuild_completed" if accepted else "odr_prebuild_failed"
    log_event(
        event_name,
        {
            "session_id": str(run_id),
            "issue_id": str(getattr(issue, "id", "")),
            "execution_profile": str(cards_runtime.get("execution_profile") or ""),
            "odr_active": True,
            "selected_model": str(selected_model),
            **dict(summary),
        },
        workspace,
    )
    return summary
