from __future__ import annotations

from typing import Any

from orket.core.cards_runtime_contract import ODR_EXECUTION_PROFILE, resolve_cards_runtime
from orket.interfaces.operator_view_support import (
    CARD_VIEW_FILTERS_V1,
    LIFECYCLE_CATEGORY_V1,
    _BLOCKED_CARD_STATUSES,
    _COMPLETED_CARD_STATUSES,
    _REVIEW_CARD_STATUSES,
    _RUNNING_CARD_STATUSES,
    _TERMINAL_FAILURE_CATEGORIES,
    _dict,
    _optional_int,
    _reason_codes,
    _status_token,
    _text,
    _text_list,
    card_filter_bucket,
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
    issue_count: int = 0,
) -> dict[str, Any]:
    normalized_summary = _dict(summary)
    normalized_artifacts = _dict(artifacts)
    classification = _classify_run_outcome(summary=normalized_summary, artifacts=normalized_artifacts, status=status)
    return {
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
    issue_count: int = 0,
) -> dict[str, Any]:
    normalized_summary = _dict(summary)
    normalized_artifacts = _dict(artifacts)
    classification = _classify_run_outcome(summary=normalized_summary, artifacts=normalized_artifacts, status=status)
    packet1 = _dict(normalized_summary.get("truthful_runtime_packet1"))
    packet1_provenance = _dict(packet1.get("provenance"))
    cards_runtime = _cards_runtime(normalized_summary)
    control_plane = _dict(normalized_summary.get("control_plane"))
    return {
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


def build_card_list_item_view(*, card: Any, run_view: dict[str, Any] | None) -> dict[str, Any]:
    payload = _card_payload(card)
    filter_bucket = card_filter_bucket(
        raw_status=_status_token(payload.get("status")),
        lifecycle_category=_text((run_view or {}).get("lifecycle_category")),
    )
    primary_status = "failed" if filter_bucket == "terminal_failure" else filter_bucket
    summary = card_summary_text(run_summary=_text((run_view or {}).get("summary")), filter_bucket=filter_bucket)
    reason_codes = [f"card.status.{_status_token(payload.get('status')) or 'unknown'}"]
    if run_view is not None:
        reason_codes.extend(_reason_codes(run_view.get("reason_codes")))
    return {
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
) -> dict[str, Any]:
    payload = _card_payload(card)
    runtime = resolve_cards_runtime(issue=_IssueViewShim(payload))
    list_item = build_card_list_item_view(card=payload, run_view=run_view)
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


def _classify_run_outcome(*, summary: dict[str, Any], artifacts: dict[str, Any], status: str | None) -> dict[str, Any]:
    raw_status = _text(status) or _text(summary.get("status"))
    status_token = raw_status.lower()
    packet1 = _dict(summary.get("truthful_runtime_packet1"))
    packet1_provenance = _dict(packet1.get("provenance"))
    cards_runtime = _cards_runtime(summary)
    execution_profile = _text(summary.get("execution_profile")) or _text(cards_runtime.get("execution_profile"))
    stop_reason = _text(summary.get("stop_reason")) or _text(cards_runtime.get("stop_reason"))
    failure_reason = _text(summary.get("failure_reason"))
    primary_output_kind = _text(packet1_provenance.get("primary_output_kind")) or "none"
    truth_classification = _text(packet1_provenance.get("truth_classification"))
    cards_resolution_state = _text(summary.get("cards_runtime_resolution_state")) or _text(cards_runtime.get("resolution_state"))
    verification = _verification_view(summary=summary, artifacts=artifacts)
    degraded = bool(summary.get("is_degraded")) or truth_classification == "degraded"
    reason_codes: list[str] = []
    if cards_resolution_state and cards_resolution_state != "resolved":
        degraded = True
        reason_codes.append(f"cards_runtime.{cards_resolution_state}")
    if stop_reason:
        reason_codes.append(f"run.stop_reason.{stop_reason.lower()}")
    if failure_reason:
        reason_codes.append(f"run.failure_reason.{failure_reason.lower()}")
    lifecycle_category = ""
    primary_status = "unknown"
    if status_token in {"failed", "terminal_failure"}:
        primary_status = "failed"
        if (execution_profile == ODR_EXECUTION_PROFILE or bool(summary.get("odr_active")) or bool(cards_runtime.get("odr_active"))) and primary_output_kind == "none":
            lifecycle_category = "prebuild_blocked"
            primary_status = "blocked"
        else:
            lifecycle_category = "artifact_run_failed"
    elif status_token in {"done", "completed"}:
        primary_status = "completed"
        if degraded:
            lifecycle_category = "degraded_completed"
        elif verification["status"] == "verified":
            lifecycle_category = "artifact_run_verified"
        else:
            lifecycle_category = "artifact_run_completed_unverified"
    elif status_token in {"started", "in_progress", "executing"}:
        primary_status = "running"
    elif status_token == "incomplete":
        primary_status = "open"
    elif status_token in {"canceled", "cancelled", "operator_blocked"}:
        primary_status = "blocked"
    else:
        primary_status = status_token or "unknown"
    if lifecycle_category:
        reason_codes.insert(0, f"run.lifecycle.{lifecycle_category}")
    summary_text = _run_summary_text(
        lifecycle_category=lifecycle_category,
        primary_status=primary_status,
        degraded=degraded,
        verification=verification,
    )
    return {
        "raw_status": raw_status or "unknown",
        "primary_status": primary_status,
        "degraded": degraded,
        "summary": summary_text,
        "reason_codes": _reason_codes(reason_codes),
        "next_action": _run_next_action(lifecycle_category=lifecycle_category, primary_status=primary_status, degraded=degraded),
        "lifecycle_category": lifecycle_category or None,
        "execution_profile": execution_profile or None,
        "stop_reason": stop_reason or None,
        "failure_reason": failure_reason or None,
        "verification": verification,
    }


def _verification_view(*, summary: dict[str, Any], artifacts: dict[str, Any]) -> dict[str, Any]:
    packet2 = _dict(summary.get("truthful_runtime_packet2"))
    source_attribution = _dict(packet2.get("source_attribution"))
    synthesis_status = _text(source_attribution.get("synthesis_status")).lower()
    if synthesis_status == "verified":
        return {
            "status": "verified",
            "summary": "Verification evidence is present and verified.",
            "reason_codes": ["verification.source_attribution_verified"],
        }
    if synthesis_status == "optional_unverified":
        return {
            "status": "unverified",
            "summary": "Run completed without verified source attribution.",
            "reason_codes": ["verification.source_attribution_optional_unverified"],
        }
    if synthesis_status == "blocked":
        return {
            "status": "blocked",
            "summary": "Verification is blocked by missing attribution requirements.",
            "reason_codes": ["verification.source_attribution_blocked"],
        }
    if _text(artifacts.get("runtime_verification_path")):
        return {
            "status": "support_only",
            "summary": "Support verification artifacts exist, but no verified attribution summary was recorded.",
            "reason_codes": ["verification.support_only"],
        }
    return {
        "status": "not_available",
        "summary": "No verification summary is available.",
        "reason_codes": ["verification.not_available"],
    }


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
        return "Completed with output, but verification is still unverified."
    if lifecycle_category == "artifact_run_verified":
        return "Completed with verified evidence."
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
        dumped = card.model_dump()
        return dumped if isinstance(dumped, dict) else {}
    return dict(getattr(card, "__dict__", {}) or {})


class _IssueViewShim:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.seat = _text(payload.get("seat"))
        self.params = _dict(payload.get("params"))
