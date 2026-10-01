"""Small-project team policy values and seat mutation, without an orchestrator proxy."""

from typing import Any

from orket.application.services import orchestrator_runtime_policy as orchestrator_policy
from orket.runtime.config import settings
from orket.schema import SeatConfig, TeamConfig


def small_project_issue_threshold(organization: Any) -> int:
    raw = 3
    if organization and isinstance(getattr(organization, "process_rules", None), dict):
        raw = organization.process_rules.get("small_project_issue_threshold", 3)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 3


def should_auto_inject_small_project_reviewer(organization: Any) -> bool:
    return bool(
        settings.resolve_bool(
            "ORKET_SMALL_PROJECT_AUTO_INJECT_REVIEWER",
            process_rules=orchestrator_policy.organization_process_rules(organization),
            process_key="small_project_auto_inject_code_reviewer",
            default=False,
        )
    )


def small_project_reviewer_seat_name(organization: Any) -> str:
    if organization and isinstance(getattr(organization, "process_rules", None), dict):
        configured = str(
            organization.process_rules.get("small_project_auto_inject_reviewer_seat_name", "auto_code_reviewer") or ""
        ).strip()
        if configured:
            return configured
    return "auto_code_reviewer"


def auto_inject_small_project_reviewer_seat(organization: Any, team: TeamConfig) -> str:
    seat_name = small_project_reviewer_seat_name(organization)
    seats = getattr(team, "seats", {}) or {}
    existing = seats.get(seat_name)
    if existing is None:
        seats[seat_name] = SeatConfig(name="Auto Injected Code Reviewer", roles=["code_reviewer"])
        return str(seat_name)
    existing_roles = list(getattr(existing, "roles", []) or [])
    normalized_roles = {str(role).strip().lower() for role in existing_roles if str(role).strip()}
    if "code_reviewer" not in normalized_roles:
        existing.roles = existing_roles + ["code_reviewer"]
    return str(seat_name)


def project_team_policy(team: Any, *, issue_count: int, threshold: int, active: bool, variant: str) -> dict[str, Any]:
    builder_role = variant if variant in {"coder", "architect"} else "coder"
    reviewer_seat = next(
        (
            seat_name
            for seat_name, seat_obj in (getattr(team, "seats", {}) or {}).items()
            if "code_reviewer" in list(getattr(seat_obj, "roles", []) or [])
        ),
        None,
    )
    builder_role_aliases = {builder_role}
    if builder_role == "architect":
        builder_role_aliases.add("lead_architect")
    builder_seat = next(
        (
            seat_name
            for seat_name, seat_obj in (getattr(team, "seats", {}) or {}).items()
            if builder_role_aliases.intersection(
                {str(role).strip() for role in list(getattr(seat_obj, "roles", []) or []) if str(role).strip()}
            )
        ),
        builder_role,
    )
    return {
        "active": bool(active),
        "issue_count": issue_count,
        "threshold": threshold,
        "variant": variant,
        "builder_role": builder_role,
        "builder_seat": builder_seat,
        "reviewer_seat": reviewer_seat,
    }
