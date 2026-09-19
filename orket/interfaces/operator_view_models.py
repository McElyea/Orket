from __future__ import annotations

from typing import Any

from orket.application.services.operator_completion_service import card_filter_bucket
from orket.application.services.operator_runtime_service import classify_operator_run, inspect_operator_card_runtime
from orket.interfaces.operator_view_support import (
    CARD_VIEW_FILTERS_V1,
    _dict,
    _optional_int,
    _reason_codes,
    _status_token,
    _text,
    _text_list,
    card_next_action,
    card_summary_text,
    last_run_summary,
)


def build_run_history_item_view(
    *,
    session_id: str,
    status: str | None,
    summary: Any,
    artifacts: Any,
    completion: dict[str, Any],
    issue_count: int = 0,
) -> dict[str, Any]:
    normalized_summary = _dict(summary)
    classification = _classify_run_outcome(summary=normalized_summary, status=status, completion=completion)
    return {
        **completion,
        "session_id": str(session_id or "").strip(),
        "raw_status": classification["raw_status"],
        "primary_status": classification["primary_status"],
        "degraded": classification["degraded"],
        "summary": classification["summary"],
        "reason_codes": classification["reason_codes"],
        "next_action": classification["next_action"],
        "lifecycle_category": classification["lifecycle_category"],
        "execution_profile": classification["execution_profile"],
        "stop_reason": classification["stop_reason"],
        "verification_status": classification["verification"]["status"],
        "verification_summary": classification["verification"]["summary"],
        "issue_count": max(0, int(issue_count or 0)),
    }


def build_run_detail_view(
    *,
    session_id: str,
    status: str | None,
    summary: Any,
    artifacts: Any,
    completion: dict[str, Any],
    issue_count: int = 0,
) -> dict[str, Any]:
    normalized_summary = _dict(summary)
    normalized_artifacts = _dict(artifacts)
    classification = _classify_run_outcome(summary=normalized_summary, status=status, completion=completion)
    packet1 = _dict(normalized_summary.get("truthful_runtime_packet1"))
    packet1_provenance = _dict(packet1.get("provenance"))
    cards_runtime = _cards_runtime(normalized_summary)
    control_plane = _dict(normalized_summary.get("control_plane"))
    return {
        **completion,
        "session_id": str(session_id or "").strip(),
        "raw_status": classification["raw_status"],
        "primary_status": classification["primary_status"],
        "degraded": classification["degraded"],
        "summary": classification["summary"],
        "reason_codes": classification["reason_codes"],
        "next_action": classification["next_action"],
        "lifecycle_category": classification["lifecycle_category"],
        "execution_profile": classification["execution_profile"],
        "stop_reason": classification["stop_reason"],
        "failure_reason": classification["failure_reason"],
        "issue_count": max(0, int(issue_count or 0)),
        "verification": classification["verification"],
        "source_attribution": _dict(_dict(normalized_summary.get("truthful_runtime_packet2")).get("source_attribution")),
        "provenance": {
            "truth_classification": _text(packet1_provenance.get("truth_classification")),
            "primary_output_kind": _text(packet1_provenance.get("primary_output_kind")) or "none",
            "primary_output_id": _text(packet1_provenance.get("primary_output_id")),
        },
        "key_artifacts": _key_artifacts(summary=normalized_summary, artifacts=normalized_artifacts),
        "artifact_contract": _artifact_contract_view(_dict(cards_runtime.get("artifact_contract"))),
        "odr_state": _odr_state_view(cards_runtime=cards_runtime, summary=normalized_summary),
        "control_plane": {
            "run_id": _text(control_plane.get("run_id")),
            "run_state": _text(control_plane.get("run_state")),
        },
    }


def build_card_list_item_view(*, card: Any, run_view: dict[str, Any] | None, completion: dict[str, Any]) -> dict[str, Any]:
    payload = _card_payload(card)
    filter_bucket = card_filter_bucket(
        raw_status=_status_token(payload.get("status")),
        lifecycle_category=_text((run_view or {}).get("lifecycle_category")),
        completion_accepted=completion["completion_accepted"],
    )
    primary_status = "failed" if filter_bucket == "terminal_failure" else filter_bucket
    summary = card_summary_text(filter_bucket=filter_bucket)
    reason_codes = [f"card.status.{_status_token(payload.get('status')) or 'unknown'}"]
    if run_view is not None:
        reason_codes.extend(_reason_codes(run_view.get("reason_codes")))
    return {
        **completion,
        "card_id": _text(payload.get("id")),
        "session_id": _text(payload.get("session_id")),
        "build_id": _text(payload.get("build_id")),
        "title": _text(payload.get("summary")) or _text(payload.get("name")),
        "seat": _text(payload.get("seat")),
        "raw_status": _status_token(payload.get("status")),
        "filter_bucket": filter_bucket,
        "primary_status": primary_status,
        "degraded": bool(run_view and run_view.get("degraded")),
        "summary": summary,
        "reason_codes": _reason_codes(reason_codes),
        "next_action": card_next_action(
            run_primary_status=_text((run_view or {}).get("primary_status")),
            run_next_action=_text((run_view or {}).get("next_action")),
            filter_bucket=filter_bucket,
        ),
        "last_run": last_run_summary(run_view),
    }


def build_card_detail_view(
    *,
    card: Any,
    history: Any,
    comments: Any,
    run_view: dict[str, Any] | None,
    completion: dict[str, Any],
) -> dict[str, Any]:
    payload = _card_payload(card)
    runtime = inspect_operator_card_runtime(payload)
    list_item = build_card_list_item_view(card=payload, run_view=run_view, completion=completion)
    return {
        **list_item,
        "description": _text(payload.get("description")),
        "assignee": _text(payload.get("assignee")),
        "priority": payload.get("priority"),
        "artifact_contract": _artifact_contract_view(_dict(runtime.get("artifact_contract"))),
        "execution_profile": _text(runtime.get("execution_profile")),
        "run_action": {
            "label": "Rerun" if run_view is not None else "Run",
            "endpoint": "/v1/system/run-active",
            "request_body": {
                "issue_id": _text(payload.get("id")),
                "build_id": _text(payload.get("build_id")) or None,
                "type": "issue",
            },
        },
        "history_count": len(history) if isinstance(history, list) else 0,
        "comments_count": len(comments) if isinstance(comments, list) else 0,
        "run": dict(run_view) if isinstance(run_view, dict) else None,
    }


def card_view_matches_filter(view: dict[str, Any], filter_name: str | None) -> bool:
    normalized = _text(filter_name).lower()
    if not normalized:
        return True
    return normalized in CARD_VIEW_FILTERS_V1 and normalized == _text(view.get("filter_bucket")).lower()


def _classify_run_outcome(*, summary: dict[str, Any], status: str | None, completion: dict[str, Any]) -> dict[str, Any]:
    classification = classify_operator_run(summary=summary, status=status, completion=completion)
    lifecycle = classification["lifecycle_category"] or ""
    primary = classification["primary_status"]
    degraded = classification["degraded"]
    return {**classification,
            "summary": _run_summary_text(lifecycle_category=lifecycle, primary_status=primary,
                                         degraded=degraded, verification=classification["verification"]),
            "next_action": _run_next_action(lifecycle_category=lifecycle, primary_status=primary, degraded=degraded)}


def _key_artifacts(*, summary: dict[str, Any], artifacts: dict[str, Any]) -> list[str]:
    packet1 = _dict(summary.get("truthful_runtime_packet1"))
    packet1_provenance = _dict(packet1.get("provenance"))
    cards_runtime = _cards_runtime(summary)
    candidates = [
        _text(packet1_provenance.get("primary_output_id")),
        _text(cards_runtime.get("odr_artifact_path")),
        _text(artifacts.get("runtime_verification_path")),
        _text(artifacts.get("run_summary_path")),
    ]
    result: list[str] = []
    for item in candidates:
        if item and item not in result:
            result.append(item)
    return result


def _artifact_contract_view(contract: dict[str, Any]) -> dict[str, Any]:
    if not contract:
        return {}
    return {
        "kind": _text(contract.get("kind")) or "none",
        "primary_output": _text(contract.get("primary_output")),
        "entrypoint_path": _text(contract.get("entrypoint_path")),
        "required_write_paths": _text_list(contract.get("required_write_paths")),
        "review_read_paths": _text_list(contract.get("review_read_paths")),
        "deployment_enabled": bool(contract.get("deployment_enabled")),
    }


def _odr_state_view(*, cards_runtime: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    if not cards_runtime and not bool(summary.get("odr_active")):
        return {}
    return {
        "active": bool(summary.get("odr_active")) or bool(cards_runtime.get("odr_active")),
        "audit_mode": _text(summary.get("audit_mode")) or _text(cards_runtime.get("audit_mode")),
        "valid": bool(summary.get("odr_valid")) if "odr_valid" in summary or "odr_valid" in cards_runtime else None,
        "pending_decisions": _optional_int(summary.get("odr_pending_decisions"), cards_runtime.get("odr_pending_decisions")),
        "stop_reason": _text(summary.get("odr_stop_reason")) or _text(cards_runtime.get("odr_stop_reason")),
        "artifact_path": _text(summary.get("odr_artifact_path")) or _text(cards_runtime.get("odr_artifact_path")),
        "last_valid_round_index": _optional_int(
            summary.get("last_valid_round_index"),
            cards_runtime.get("last_valid_round_index"),
        ),
        "last_emitted_round_index": _optional_int(
            summary.get("last_emitted_round_index"),
            cards_runtime.get("last_emitted_round_index"),
        ),
    }


def _run_summary_text(
    *,
    lifecycle_category: str,
    primary_status: str,
    degraded: bool,
    verification: dict[str, Any],
) -> str:
    if lifecycle_category == "prebuild_blocked":
        return "Blocked in prebuild before an artifact-producing run started."
    if lifecycle_category == "artifact_run_failed":
        return "Artifact-producing run failed before completion."
    if lifecycle_category == "artifact_run_completed_unverified":
        return "Lifecycle is completed; declared acceptance is unverified."
    if lifecycle_category == "artifact_run_verified":
        return "Completed with retained evidence for the declared acceptance criteria."
    if lifecycle_category == "degraded_completed":
        return "Completed, but degraded evidence limits how much trust to place in the result."
    if primary_status == "running":
        return "Run is still active."
    if primary_status == "open":
        return "Run has not reached a terminal outcome."
    if degraded:
        return "Run state is degraded."
    return "Run state is available."


def _run_next_action(*, lifecycle_category: str, primary_status: str, degraded: bool) -> str:
    if lifecycle_category == "prebuild_blocked":
        return "review_prebuild_findings"
    if lifecycle_category == "artifact_run_failed":
        return "inspect_failure_and_rerun"
    if lifecycle_category == "artifact_run_completed_unverified":
        return "complete_verification"
    if lifecycle_category == "artifact_run_verified":
        return "inspect_verified_output"
    if lifecycle_category == "degraded_completed":
        return "inspect_degraded_reasons"
    if primary_status == "running":
        return "monitor_run"
    if primary_status == "blocked":
        return "resolve_blocker"
    return "inspect_run" if degraded else "continue_operations"


def _cards_runtime(summary: dict[str, Any]) -> dict[str, Any]:
    return _dict(summary.get("cards_runtime"))


def _card_payload(card: Any) -> dict[str, Any]:
    if isinstance(card, dict):
        return dict(card)
    if hasattr(card, "model_dump"):
        dumped = card.model_dump(mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return dict(getattr(card, "__dict__", {}) or {})
