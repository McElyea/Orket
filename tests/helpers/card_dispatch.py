"""Explicit application-service doubles for isolated orchestration unit tests."""
from __future__ import annotations

from types import SimpleNamespace

from orket.application.services.decision_context_service import capture_planning_inputs
from orket.application.workflows import orchestrator_ops


def install_dispatch_snapshot_stub(monkeypatch):
    async def read_snapshot(*, cards, build_id):
        backlog = await cards.get_by_build(build_id)
        ready = await cards.independent_ready(build_id)
        def plan(planner, target_issue_id):
            by_id = {card.id: card for card in backlog}
            return [by_id[card.id] for card in planner.plan(capture_planning_inputs(backlog, ready, target_issue_id))]
        return SimpleNamespace(backlog=backlog, dependency_rejections={}, plan=plan)

    async def dependency_context(*, cards, issue):
        return {"depends_on": list(issue.depends_on or []), "dependency_count": len(issue.depends_on or []),
                "dependency_statuses": {}, "unresolved_dependencies": []}

    monkeypatch.setattr(orchestrator_ops, "read_card_dispatch_snapshot", read_snapshot)
    monkeypatch.setattr(orchestrator_ops, "build_card_dependency_context", dependency_context)
