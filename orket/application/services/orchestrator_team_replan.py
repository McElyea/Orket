"""One owner for replan counts; scheduler effects use operation-specific ports."""

from collections import defaultdict
from collections.abc import Awaitable, Callable
from types import SimpleNamespace
from typing import Any

from orket.application.services.orchestrator_scheduler_control_plane_service import (
    OrchestratorSchedulerControlPlaneService,
)
from orket.core.contracts.repositories import CardRepository
from orket.exceptions import CardNotFound, ExecutionFailed
from orket.naming import sanitize_name
from orket.schema import CardStatus

Transition = Callable[..., Awaitable[None]]
CardSource = Callable[[], CardRepository]
ChildPublicationSource = Callable[[], OrchestratorSchedulerControlPlaneService | None]
Emit = Callable[[str, dict[str, Any]], None]
SelectTeam = Callable[[Any, Any], dict[str, Any]]


async def propagate_dependency_blocks(
    backlog: list[Any], run_id: str, *, request_transition: Transition, emit: Emit
) -> int:
    blocker_statuses = {CardStatus.BLOCKED, CardStatus.CANCELED, CardStatus.GUARD_REJECTED}
    status_by_id = {getattr(issue, "id", ""): getattr(issue, "status", None) for issue in backlog}
    propagated = []
    for issue in backlog:
        if getattr(issue, "status", None) != CardStatus.READY:
            continue
        depends_on = list(getattr(issue, "depends_on", []) or [])
        if not depends_on:
            continue
        blocked_by = [dep_id for dep_id in depends_on if status_by_id.get(dep_id) in blocker_statuses]
        if not blocked_by:
            continue
        await request_transition(
            issue=issue,
            target_status=CardStatus.BLOCKED,
            reason="dependency_blocked",
            metadata={"run_id": run_id, "blocked_by": blocked_by},
        )
        propagated.append({"issue_id": issue.id, "blocked_by": blocked_by})
    if propagated:
        emit("dependency_block_propagated", {"run_id": run_id, "updates": propagated})
    return len(propagated)


class TeamReplanScheduler:
    """Retains only replan counts across epic executions; effects stay with their owners."""

    def __init__(self) -> None:
        self._counts: defaultdict[str, int] = defaultdict(int)

    async def maybe_schedule(
        self,
        backlog: list[Any],
        run_id: str,
        active_build: str,
        team: Any,
        *,
        request_transition: Transition,
        cards: CardSource,
        select_team: SelectTeam,
        child_publication: ChildPublicationSource,
        emit: Emit,
    ) -> bool:
        triggering_issues: list[Any] = []
        for issue in backlog:
            seat = str(getattr(issue, "seat", "") or "").strip().lower()
            if seat != "requirements_analyst":
                continue
            params = getattr(issue, "params", None)
            if isinstance(params, dict) and bool(params.get("replan_requested")):
                triggering_issues.append(issue)
        if not triggering_issues:
            return False
        current_count = int(self._counts.get(run_id, 0))
        next_count = current_count + 1
        if next_count > 3:
            await _block_after_limit(
                backlog, run_id, active_build, current_count, request_transition=request_transition, emit=emit
            )
        self._counts[run_id] = next_count
        run_prefix = sanitize_name(str(run_id or "run"))[:6].upper() or "RUN"
        replan_issue_id = f"REPLAN-{run_prefix}-{next_count}"
        small_policy = select_team(SimpleNamespace(issues=backlog), team)
        replan_seat = str(small_policy.get("builder_seat") or "architect")
        await _save_replan_issue(cards, replan_issue_id, replan_seat, active_build, run_id, next_count)
        await _publish_replan_child(
            child_publication, run_id, replan_issue_id, active_build, replan_seat, triggering_issues, next_count
        )
        await _clear_requests(triggering_issues, cards)
        emit(
            "team_replan_scheduled",
            {
                "run_id": run_id,
                "active_build": active_build,
                "replan_issue_id": replan_issue_id,
                "replan_count": next_count,
                "seat": replan_seat,
                "trigger_issue_ids": [getattr(item, "id", "") for item in triggering_issues],
            },
        )
        return True


async def _block_after_limit(
    backlog: list[Any],
    run_id: str,
    active_build: str,
    current_count: int,
    *,
    request_transition: Transition,
    emit: Emit,
) -> None:
    for issue in backlog:
        issue_id = getattr(issue, "id", None)
        if not issue_id:
            continue
        try:
            await request_transition(
                issue=issue,
                target_status=CardStatus.BLOCKED,
                reason="team_replan_limit_exceeded",
                metadata={"run_id": run_id, "replan_count": current_count},
            )
        except (CardNotFound, ExecutionFailed, ValueError, TypeError, RuntimeError, OSError):
            continue
    emit(
        "team_replan_terminal_failure",
        {"run_id": run_id, "active_build": active_build, "replan_count": current_count, "limit": 3},
    )
    raise ExecutionFailed("TEAM_REPLAN_LIMIT_EXCEEDED: requirements changed too many times (limit=3).")


async def _save_replan_issue(
    cards: CardSource, replan_issue_id: str, replan_seat: str, active_build: str, run_id: str, next_count: int
) -> None:
    await cards().save(
        {
            "id": replan_issue_id,
            "summary": "Re-evaluate team composition after requirement change",
            "seat": replan_seat,
            "type": "issue",
            "status": CardStatus.READY,
            "priority": 3.0,
            "build_id": active_build,
            "session_id": run_id,
            "params": {"card_kind": "team_replan", "replan_count": next_count},
        }
    )


async def _publish_replan_child(
    child_publication: ChildPublicationSource,
    run_id: str,
    replan_issue_id: str,
    active_build: str,
    replan_seat: str,
    triggering_issues: list[Any],
    next_count: int,
) -> None:
    scheduler_control_plane = child_publication()
    if scheduler_control_plane is not None:
        await scheduler_control_plane.publish_child_issue_creation(
            session_id=run_id,
            issue_id=replan_issue_id,
            active_build=active_build,
            seat_name=replan_seat,
            relationship_class="team_replan",
            trigger_issue_ids=[str(getattr(item, "id", "") or "").strip() for item in triggering_issues],
            metadata={"replan_count": next_count},
        )


async def _clear_requests(triggering_issues: list[Any], cards: CardSource) -> None:
    for issue in triggering_issues:
        params = getattr(issue, "params", None)
        if isinstance(params, dict):
            params["replan_requested"] = False
        try:
            if hasattr(issue, "model_dump"):
                await cards().save(issue.model_dump())
            else:
                await cards().save(dict(issue.__dict__))
        except (CardNotFound, ExecutionFailed, ValueError, TypeError, RuntimeError, OSError):
            continue
