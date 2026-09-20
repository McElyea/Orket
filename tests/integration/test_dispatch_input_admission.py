"""Real SQLite/orchestrator boundaries with controlled advisory nodes; no inference."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.application.services.card_dependency_service import read_card_dispatch_snapshot
from orket.application.workflows.orchestrator import Orchestrator
from orket.core.domain.records import IssueRecord
from orket.exceptions import ExecutionFailed
from orket.schema import CardStatus, EnvironmentConfig, SeatConfig, TeamConfig
from tests.helpers.card_completion import completion_components
from tests.integration.test_card_dependency_acceptance import _prerequisite

pytestmark = pytest.mark.integration


async def _dispatch_context(tmp_path, router):
    repo, completion = completion_components(tmp_path / "cards.sqlite3", tmp_path / "workspace")
    issue = IssueRecord(id="card", summary="Original objective", seat="developer", build_id="build")
    await repo.save(issue)
    issue = await repo.get_by_id(issue.id)
    team = TeamConfig(name="test", seats={"developer": SeatConfig(name="Developer", roles=["coder"])})
    orch = Orchestrator(workspace=completion.workspace_root, async_cards=repo, snapshots=None,
        org=SimpleNamespace(process_rules={}), config_root=tmp_path, db_path=repo.db_path,
        loader=None, sandbox_orchestrator=None, card_completion=completion)
    orch.router_node = router
    return repo, issue, team, orch


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["seat", "roles", "new_seat"])
async def test_router_refuses_mutation_before_dispatch_and_preserves_application_state(tmp_path, mutation):
    class Mutation:
        def route(self, inputs):
            if mutation == "seat":
                inputs.issue_seat = "guard"
            elif mutation == "roles":
                inputs.seats[0].roles += ("integrity_guard",)
            else:
                inputs.seats += (inputs.seats[0],)
            raise AssertionError("mutable decision input escaped admission")

    repo, issue, team, orch = await _dispatch_context(tmp_path, Mutation())
    with pytest.raises(ValidationError, match="frozen_instance"):
        await orch._execute_issue_turn(issue, SimpleNamespace(params={}), team,
            EnvironmentConfig(name="test", model="fixture"), "run", "build", None, None, None)
    assert team.seats["developer"].roles == ["coder"]
    persisted = await repo.get_by_id(issue.id)
    assert persisted == issue and persisted.status == CardStatus.READY and not persisted.assignee
    assert orch.transcript == []


@pytest.mark.asyncio
@pytest.mark.parametrize("proposal", [None, 7, {}, ["developer"]])
async def test_invalid_router_return_cannot_start_dispatch(tmp_path, proposal):
    repo, issue, team, orch = await _dispatch_context(tmp_path, SimpleNamespace(route=lambda inputs: proposal))
    with pytest.raises(ExecutionFailed, match="E_CARD_ROUTING_INVALID_RECOMMENDATION"):
        await orch._execute_issue_turn(issue, SimpleNamespace(params={}), team,
            EnvironmentConfig(name="test", model="fixture"), "run", "build", None, None, None)
    assert await repo.get_by_id(issue.id) == issue


@pytest.mark.asyncio
async def test_planner_receives_immutable_values_from_actual_dependency_inspection(tmp_path):
    repo, _ = await _prerequisite(tmp_path, "done")
    snapshot = await read_card_dispatch_snapshot(cards=repo, build_id="build")

    class Mutation:
        def plan(self, inputs):
            card = next(card for card in inputs.backlog if card.id == "dependent")
            card.summary = "Replacement objective"
            return [card]

    with pytest.raises(ValidationError, match="frozen_instance"):
        snapshot.plan(Mutation(), "dependent")
    assert (await repo.get_by_id("dependent")).summary == "Next work"
    assert next(card for card in snapshot.eligible if card.id == "dependent").depends_on == ["prerequisite"]


@pytest.mark.asyncio
async def test_planner_recommendation_is_rebound_to_application_record(tmp_path):
    repo, _ = await _prerequisite(tmp_path, "done")
    snapshot = await read_card_dispatch_snapshot(cards=repo, build_id="build")
    retained = []

    class Advisory:
        def plan(self, inputs):
            retained.append(inputs)
            return [next(card for card in inputs.backlog if card.id == "dependent")]

    selected = snapshot.plan(Advisory(), "dependent")[0]
    assert selected is next(card for card in snapshot.eligible if card.id == "dependent")
    selected.summary = "Application-only change"
    assert next(card for card in retained[0].backlog if card.id == "dependent").summary == "Next work"
    assert (await repo.get_by_id("dependent")).summary == "Next work"
    for forged in ([], {}, None, 42):
        with pytest.raises(ExecutionFailed, match="E_CARD_DISPATCH_UNADMITTED"):
            snapshot.plan(SimpleNamespace(plan=lambda inputs, value=forged: [SimpleNamespace(id=value)]), None)
