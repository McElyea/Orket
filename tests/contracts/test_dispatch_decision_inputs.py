"""Contract proof for immutable planning/routing facts and deterministic recommendations."""
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.application.services.decision_context_service import capture_planning_inputs, capture_routing_input
from orket.core.contracts.decision_inputs import PlanningCardInput, PlanningInput, RoutingInput, RoutingSeatInput
from orket.core.domain.records import IssueRecord
from orket.decision_nodes.builtins import DefaultPlannerNode, DefaultRouterNode
from orket.schema import CardStatus, SeatConfig, TeamConfig

pytestmark = pytest.mark.contract


def test_planning_capture_detaches_mutable_records_and_collections():
    card = IssueRecord(id="card", summary="Original", seat="developer", depends_on=["prerequisite"],
                       params={"runtime_only": {"value": 1}})
    records = [card]
    captured = capture_planning_inputs(records, records, "card")
    card.summary, card.depends_on[0] = "Changed", "new-prerequisite"
    records.clear()
    assert captured.backlog[0].summary == "Original"
    assert captured.backlog[0].depends_on == ("prerequisite",)
    assert not hasattr(captured.backlog[0], "params")
    with pytest.raises(ValidationError, match="frozen_instance"):
        captured.target_issue_id = "other"
    with pytest.raises(ValidationError, match="frozen_instance"):
        captured.backlog[0].summary = "Other"
    with pytest.raises(AttributeError):
        captured.independent_ready.append(captured.backlog[0])


def test_direct_contract_construction_copies_nested_mutable_sequences():
    dependencies, roles = ["a"], ["coder"]
    card = PlanningCardInput(id="card", status=CardStatus.READY, depends_on=dependencies)
    rows = [card]
    planning = PlanningInput(backlog=rows, independent_ready=rows)
    routing = RoutingInput(issue_id="card", issue_seat="developer", is_review_turn=False,
                           seats=[RoutingSeatInput(name="developer", roles=roles)])
    rows.clear()
    dependencies.append("b")
    roles.append("integrity_guard")
    assert planning.backlog == (card,) and card.depends_on == ("a",)
    assert routing.seats[0].roles == ("coder",)
    with pytest.raises(ValidationError, match="extra_forbidden"):
        PlanningCardInput(id="card", status=CardStatus.READY, params={})
    with pytest.raises(ValidationError):
        PlanningInput(backlog=[SimpleNamespace(id="card")], independent_ready=[])


@pytest.mark.parametrize("review", [False, True])
def test_router_uses_captured_team_order_and_roles(review):
    issue = SimpleNamespace(id="card", seat="developer")
    team = TeamConfig(name="test", seats={
        "guard_first": SeatConfig(name="First", roles=["integrity_guard"]),
        "guard_second": SeatConfig(name="Second", roles=["integrity_guard"]),
        "developer": SeatConfig(name="Developer", roles=["coder"]),
    })
    inputs = capture_routing_input(issue, team, review)
    issue.seat = "changed"
    team.seats["guard_first"].roles.clear()
    team.seats.clear()
    node = DefaultRouterNode()
    assert node.route(inputs) == ("guard_first" if review else "developer")
    assert node.route(inputs) == node.route(inputs.model_copy(deep=True))
    with pytest.raises(ValidationError, match="frozen_instance"):
        inputs.seats[0].roles = ("replacement",)


@pytest.mark.parametrize("status", list(CardStatus))
@pytest.mark.parametrize("independent", [False, True])
def test_targeted_planner_status_parity(status, independent):
    card = PlanningCardInput(id="card", status=status)
    inputs = PlanningInput(backlog=[card], independent_ready=[card] if independent else [], target_issue_id="card")
    expected = (status in {CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW}
                or (status == CardStatus.READY and independent))
    node = DefaultPlannerNode()
    assert node.plan(inputs) == ([card] if expected else [])
    assert node.plan(inputs) == node.plan(inputs.model_copy(deep=True))


def test_router_without_guard_preserves_issue_seat():
    inputs = RoutingInput(issue_id="card", issue_seat="developer", is_review_turn=True, seats=())
    assert DefaultRouterNode().route(inputs) == "developer"
