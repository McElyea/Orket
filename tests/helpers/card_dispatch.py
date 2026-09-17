"""Explicit application-service doubles for isolated orchestration unit tests."""
from __future__ import annotations

from types import SimpleNamespace

from orket.application.workflows import orchestrator_ops
from orket.decision_nodes.contracts import PlanningInput


def install_dispatch_snapshot_stub(monkeypatch):
    async def read_snapshot(*, cards, build_id):
        backlog = await cards.get_by_build(build_id)
        ready = await cards.independent_ready(build_id)
        return SimpleNamespace(backlog=backlog, dependency_rejections={}, plan=lambda planner, target_issue_id: planner.plan(
            PlanningInput(backlog=backlog, independent_ready=ready, target_issue_id=target_issue_id)))

    async def dependency_context(*, cards, issue):
        return {"depends_on": list(issue.depends_on or []), "dependency_count": len(issue.depends_on or []),
                "dependency_statuses": {}, "unresolved_dependencies": []}

    monkeypatch.setattr(orchestrator_ops, "read_card_dispatch_snapshot", read_snapshot)
    monkeypatch.setattr(orchestrator_ops, "build_card_dependency_context", dependency_context)
