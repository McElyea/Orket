from __future__ import annotations

from typing import Any

CARD_VIEW_FILTERS_V1 = ("open", "running", "blocked", "review", "terminal_failure", "completed")
LIFECYCLE_CATEGORY_V1 = (
    "prebuild_blocked",
    "artifact_run_failed",
    "artifact_run_completed_unverified",
    "artifact_run_verified",
    "degraded_completed",
)

_OPEN_CARD_STATUSES = {"ready", "waiting_for_developer", "ready_for_testing"}
_RUNNING_CARD_STATUSES = {"in_progress", "started"}
_BLOCKED_CARD_STATUSES = {"blocked", "guard_rejected", "canceled", "archived"}
_REVIEW_CARD_STATUSES = {"code_review", "awaiting_guard_review", "guard_requested_changes", "guard_approved"}
_COMPLETED_CARD_STATUSES = {"done"}
_TERMINAL_FAILURE_CATEGORIES = {"prebuild_blocked", "artifact_run_failed"}
_DEGRADED_RESOURCE_THRESHOLD = 90.0
_DEGRADED_VRAM_RATIO = 0.95


def card_filter_bucket(*, raw_status: str, lifecycle_category: str) -> str:
    if lifecycle_category in _TERMINAL_FAILURE_CATEGORIES:
        return "terminal_failure"
    if raw_status in _BLOCKED_CARD_STATUSES:
        return "blocked"
    if raw_status in _REVIEW_CARD_STATUSES:
        return "review"
    if raw_status in _COMPLETED_CARD_STATUSES:
        return "completed"
    if raw_status in _RUNNING_CARD_STATUSES:
        return "running"
    return "open"


def card_summary_text(*, run_summary: str, filter_bucket: str) -> str:
    if run_summary:
        return run_summary
    if filter_bucket == "review":
        return "Waiting on review or guard confirmation."
    if filter_bucket == "blocked":
        return "Blocked until a dependency or operator action clears."
    if filter_bucket == "running":
        return "Currently executing."
    if filter_bucket == "completed":
        return "Completed with no current run summary."
    return "Ready to run."


def card_next_action(*, run_primary_status: str, run_next_action: str, filter_bucket: str) -> str:
    if run_primary_status in {"completed", "failed", "blocked"}:
        return run_next_action or "inspect_run"
    if filter_bucket == "review":
        return "review_or_guard"
    if filter_bucket == "blocked":
        return "resolve_blocker"
    if filter_bucket == "running":
        return "monitor_run"
    return "run_card"


def last_run_summary(run_view: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(run_view, dict):
        return None
    return {
        "session_id": _text(run_view.get("session_id")),
        "primary_status": _text(run_view.get("primary_status")),
        "lifecycle_category": _text(run_view.get("lifecycle_category")) or None,
        "degraded": bool(run_view.get("degraded")),
        "summary": _text(run_view.get("summary")),
    }


def build_provider_status_view(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    items = []
    demoted_roles: list[str] = []
    for row in assignments:
        payload = _dict(row)
        role = _text(payload.get("role"))
        final_model = _text(payload.get("final_model"))
        if not role or not final_model:
            continue
        demoted = bool(payload.get("demoted"))
        if demoted:
            demoted_roles.append(role)
        items.append(
            {
                "role": role,
                "model": final_model,
                "dialect": _text(payload.get("dialect")),
                "demoted": demoted,
                "reason": _text(payload.get("reason")) or "unknown",
            }
        )
    if not items:
        return {
            "primary_status": "blocked",
            "degraded": True,
            "summary": "No active provider assignments were resolved.",
            "reason_codes": ["provider.no_assignments"],
            "next_action": "inspect_model_assignments",
            "assignment_count": 0,
            "demoted_roles": [],
            "assignments": [],
        }
    degraded = bool(demoted_roles)
    return {
        "primary_status": "degraded" if degraded else "healthy",
        "degraded": degraded,
        "summary": (
            f"{len(demoted_roles)} role assignments were demoted."
            if degraded
            else f"{len(items)} provider assignments resolved cleanly."
        ),
        "reason_codes": ["provider.assignment_demoted"] if degraded else ["provider.assignments_resolved"],
        "next_action": "inspect_model_assignments" if degraded else "continue_operations",
        "assignment_count": len(items),
        "demoted_roles": sorted(demoted_roles),
        "assignments": items,
    }


def build_system_health_view(
    *,
    heartbeat: dict[str, Any],
    metrics: dict[str, Any],
    provider_status: dict[str, Any],
) -> dict[str, Any]:
    heartbeat_status = _text(heartbeat.get("status")).lower()
    cpu_percent = _float(metrics.get("cpu_percent"))
    ram_percent = _float(metrics.get("ram_percent"))
    vram_used = _float(metrics.get("vram_gb_used"))
    vram_total = _float(metrics.get("vram_total_gb"))
    degraded = heartbeat_status != "online" or bool(provider_status.get("degraded"))
    reason_codes: list[str] = []
    if heartbeat_status != "online":
        degraded = True
        reason_codes.append(f"system.heartbeat.{heartbeat_status or 'unknown'}")
    if cpu_percent >= _DEGRADED_RESOURCE_THRESHOLD:
        degraded = True
        reason_codes.append("system.cpu_hot")
    if ram_percent >= _DEGRADED_RESOURCE_THRESHOLD:
        degraded = True
        reason_codes.append("system.ram_hot")
    if vram_total > 0.0 and (vram_used / vram_total) >= _DEGRADED_VRAM_RATIO:
        degraded = True
        reason_codes.append("system.vram_hot")
    if bool(provider_status.get("degraded")):
        reason_codes.append("system.provider_degraded")
    return {
        "primary_status": "degraded" if degraded else "online",
        "degraded": degraded,
        "summary": (
            "System is online, but capacity or provider routing is degraded."
            if degraded
            else "System is online and healthy."
        ),
        "reason_codes": _reason_codes(reason_codes or ["system.online"]),
        "next_action": "inspect_system_health" if degraded else "continue_operations",
        "timestamp": _text(metrics.get("timestamp")) or _text(heartbeat.get("timestamp")),
        "active_tasks": max(0, _int(heartbeat.get("active_tasks"))),
        "cpu_percent": cpu_percent,
        "ram_percent": ram_percent,
        "vram_gb_used": vram_used,
        "vram_total_gb": vram_total,
        "provider_status": dict(provider_status),
    }


def _status_token(value: Any) -> str:
    return _text(value).lower()


def _text(value: Any) -> str:
    return str(value or "").strip()


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    items: list[str] = []
    for item in value:
        token = _text(item)
        if token:
            items.append(token)
    return items


def _reason_codes(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    result: list[str] = []
    for item in values:
        token = _text(item)
        if token and token not in result:
            result.append(token)
    return result


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(*values: Any) -> int | None:
    for value in values:
        raw = _text(value)
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return None
