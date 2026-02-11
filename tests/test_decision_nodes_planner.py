from types import SimpleNamespace

from orket.decision_nodes.builtins import DefaultPlannerNode
from orket.decision_nodes.contracts import PlanningInput
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.schema import CardStatus


def _issue(issue_id: str, status: CardStatus):
    return SimpleNamespace(id=issue_id, status=status)


def test_default_planner_prioritizes_review_then_ready():
    planner = DefaultPlannerNode()
    backlog = [
        _issue("I1", CardStatus.READY),
        _issue("I2", CardStatus.CODE_REVIEW),
    ]
    independent_ready = [_issue("I1", CardStatus.READY)]

    candidates = planner.plan(PlanningInput(backlog=backlog, independent_ready=independent_ready))

    assert [c.id for c in candidates] == ["I2", "I1"]


def test_default_planner_target_missing_returns_empty():
    planner = DefaultPlannerNode()
    backlog = [_issue("I1", CardStatus.READY)]
    independent_ready = [_issue("I1", CardStatus.READY)]

    candidates = planner.plan(
        PlanningInput(backlog=backlog, independent_ready=independent_ready, target_issue_id="MISSING")
    )

    assert candidates == []


def test_default_planner_target_in_review_selected():
    planner = DefaultPlannerNode()
    backlog = [_issue("I1", CardStatus.CODE_REVIEW), _issue("I2", CardStatus.READY)]
    independent_ready = [_issue("I2", CardStatus.READY)]

    candidates = planner.plan(
        PlanningInput(backlog=backlog, independent_ready=independent_ready, target_issue_id="I1")
    )

    assert [c.id for c in candidates] == ["I1"]


def test_default_planner_target_ready_but_not_independent_returns_empty():
    planner = DefaultPlannerNode()
    backlog = [_issue("I1", CardStatus.READY)]
    independent_ready = []

    candidates = planner.plan(
        PlanningInput(backlog=backlog, independent_ready=independent_ready, target_issue_id="I1")
    )

    assert candidates == []


def test_default_planner_target_ready_and_independent_selected():
    planner = DefaultPlannerNode()
    backlog = [_issue("I1", CardStatus.READY)]
    independent_ready = [_issue("I1", CardStatus.READY)]

    candidates = planner.plan(
        PlanningInput(backlog=backlog, independent_ready=independent_ready, target_issue_id="I1")
    )

    assert [c.id for c in candidates] == ["I1"]


def test_registry_resolves_default_when_no_org():
    registry = DecisionNodeRegistry()
    planner = registry.resolve_planner(None)

    assert isinstance(planner, DefaultPlannerNode)


def test_registry_falls_back_to_default_for_unknown_name():
    registry = DecisionNodeRegistry()
    org = SimpleNamespace(process_rules={"planner_node": "unknown"})

    planner = registry.resolve_planner(org)

    assert isinstance(planner, DefaultPlannerNode)


def test_registry_uses_registered_planner():
    class CustomPlanner(DefaultPlannerNode):
        pass

    registry = DecisionNodeRegistry()
    custom = CustomPlanner()
    registry.register_planner("custom", custom)
    org = SimpleNamespace(process_rules={"planner_node": "custom"})

    planner = registry.resolve_planner(org)

    assert planner is custom
