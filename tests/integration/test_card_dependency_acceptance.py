"""Dependency resolution requires accepted prerequisites from the current build."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.adapters.storage.card_migrations import CARD_BOOTSTRAP_MIGRATIONS
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.application.services.card_dependency_service import read_card_dispatch_snapshot
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.workflows import orchestrator_ops
from orket.application.workflows.orchestrator import Orchestrator
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.builtins import DefaultPlannerNode
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus, IssueConfig
from tests.helpers.card_completion import complete_existing_card, completion_components
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = pytest.mark.integration


async def _select_ready(cards, build_id):
    return (await read_card_dispatch_snapshot(cards=cards, build_id=build_id)).independent_ready


async def _prerequisite(tmp_path, case):
    db = tmp_path / "cards.db"
    if case == "legacy_done":
        async with aiosqlite.connect(db) as connection:
            await SQLiteMigrationRunner(namespace="card_repository").apply(connection, CARD_BOOTSTRAP_MIGRATIONS)
            await connection.execute("INSERT INTO issues (id, summary, seat, type, priority, status, build_id) "
                                     "VALUES ('prerequisite', 'Old work', 'developer', 'issue', 2.0, 'done', 'build')")
            await connection.execute("PRAGMA user_version=1")
            await connection.commit()
    repo, service = completion_components(db, tmp_path / "workspace")
    if case not in {"legacy_done", "missing"}:
        await repo.save(IssueRecord(id="prerequisite", summary="Increment", seat="developer",
                                   build_id="foreign" if case == "foreign_build" else "build"))
        target = CardStatus.GUARD_APPROVED if case == "guard_approved" else CardStatus.DONE
        if case != "pending":
            await complete_existing_card(repo, "prerequisite", service.workspace_root, service=service, target_status=target)
        if case in {"archived", "canceled", "reopened"}:
            await repo.update_status("prerequisite", CardStatus.CODE_REVIEW if case == "reopened" else CardStatus(case))
        if case == "missing_evidence":
            await asyncio.to_thread(service.acceptance.evidence_store.db_path.unlink)
    await repo.save(IssueRecord(id="dependent", summary="Next work", seat="developer", build_id="build",
                               depends_on=["prerequisite"]))
    await repo.save(IssueRecord(id="independent", summary="Unrelated work", seat="developer", build_id="build"))
    return repo, service


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["done", "guard_approved", "archived", "canceled", "reopened", "legacy_done",
                                  "missing_evidence", "missing", "foreign_build", "pending"])
# Layer: integration
async def test_scheduler_and_turn_context_agree_on_accepted_dependencies(tmp_path, case):
    repo, _ = await _prerequisite(tmp_path, case)
    ready = await _select_ready(repo, "build")
    issue = IssueConfig.model_validate((await repo.get_by_id("dependent")).model_dump())
    context = await orchestrator_ops._build_dependency_context(SimpleNamespace(async_cards=repo), issue)
    accepted = case in {"done", "guard_approved"}
    assert ("dependent" in {card.id for card in ready}) is accepted
    assert "independent" in {card.id for card in ready}
    assert (context["unresolved_dependencies"] == []) is accepted
    assert context["depends_on"] == ["prerequisite"] and context["dependency_count"] == 1
    if accepted:
        receipt = await repo.read_completion_receipt("prerequisite")
        assert context["accepted_dependency_receipts"] == {"prerequisite": receipt.digest}
        assert not context["dependency_rejections"]
    else:
        assert not context["accepted_dependency_receipts"] and "prerequisite" in context["dependency_rejections"]


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [CardStatus.READY, CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW,
                                     CardStatus.AWAITING_GUARD_REVIEW])
# Layer: integration
async def test_targeted_planner_cannot_bypass_unaccepted_prerequisite(tmp_path, status):
    repo, _ = await _prerequisite(tmp_path, "missing_evidence")
    await repo.update_status("dependent", status)
    snapshot = await read_card_dispatch_snapshot(cards=repo, build_id="build")
    assert snapshot.plan(DefaultPlannerNode(), "dependent") == []
    assert "prerequisite" in snapshot.dependency_rejections["dependent"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["prerequisite_reopen", "dependent_edges", "dependent_state"])
# Layer: integration
async def test_dependency_drift_after_selection_stops_before_turn_effects(tmp_path, change):
    repo, service = await _prerequisite(tmp_path, "done")
    snapshot = await read_card_dispatch_snapshot(cards=repo, build_id="build")
    selected = snapshot.plan(DefaultPlannerNode(), "dependent")[0]
    error = "E_CARD_DEPENDENCY_UNSATISFIED"
    if change == "prerequisite_reopen":
        await repo.update_status("prerequisite", CardStatus.CODE_REVIEW)
    elif change == "dependent_edges":
        record = await repo.get_by_id("dependent")
        record.depends_on.append("new-prerequisite")
        await repo.save(record)
        error = "E_CARD_DEPENDENCY_INPUT_STALE"
    else:
        await repo.update_status("dependent", CardStatus.BLOCKED)
        error = "E_CARD_DISPATCH_STATE_STALE"
    orch = Orchestrator(workspace=service.workspace_root, async_cards=repo, snapshots=None,
                        org=SimpleNamespace(process_rules={}), config_root=tmp_path, db_path=repo.db_path,
                        loader=None, sandbox_orchestrator=None, card_completion=service,
        architecture_policy=ArchitecturePolicySnapshot(False),
     turn_clock=artifact_test_utc_now)
    with pytest.raises(ExecutionFailed, match=error):
        await orch._execute_issue_turn(selected, SimpleNamespace(params={}), None, None, "run", "build",
                                       None, None, None)


@pytest.mark.asyncio
# Layer: integration
async def test_planner_copies_cannot_replace_dispatch_payload_or_select_unadmitted_cards(tmp_path):
    repo, _ = await _prerequisite(tmp_path, "done")
    snapshot = await read_card_dispatch_snapshot(cards=repo, build_id="build")

    class MutatingPlanner:
        def plan(self, data):
            selected = next(card for card in data.backlog if card.id == "dependent")
            return [selected.model_copy(update={"summary": "Replace objective", "depends_on": ()})]

    selected = snapshot.plan(MutatingPlanner(), "dependent")[0]
    assert selected.summary == "Next work" and selected.depends_on == ["prerequisite"]
    for candidates in ([selected, selected], [IssueRecord(id="outside", summary="Unadmitted", seat="developer")]):
        with pytest.raises(ExecutionFailed, match="E_CARD_DISPATCH_UNADMITTED"):
            snapshot.plan(SimpleNamespace(plan=lambda data, selected_candidates=candidates: selected_candidates), None)
