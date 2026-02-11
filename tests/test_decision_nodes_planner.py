from types import SimpleNamespace

from orket.decision_nodes.builtins import (
    DefaultEvaluatorNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
)
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


def test_default_router_routes_to_issue_seat_for_non_review():
    router = DefaultRouterNode()
    issue = SimpleNamespace(seat="senior_developer")
    team = SimpleNamespace(
        seats={
            "senior_developer": SimpleNamespace(roles=["coder"]),
            "guard": SimpleNamespace(roles=["integrity_guard"]),
        }
    )

    assert router.route(issue, team, is_review_turn=False) == "senior_developer"


def test_default_router_prefers_integrity_guard_for_review():
    router = DefaultRouterNode()
    issue = SimpleNamespace(seat="senior_developer")
    team = SimpleNamespace(
        seats={
            "senior_developer": SimpleNamespace(roles=["coder"]),
            "integrity_guard": SimpleNamespace(roles=["integrity_guard"]),
        }
    )

    assert router.route(issue, team, is_review_turn=True) == "integrity_guard"


def test_default_prompt_strategy_delegates_to_model_selector():
    class FakeModelSelector:
        def select(self, role, asset_config):
            assert role == "lead_architect"
            assert asset_config == "epic"
            return "qwen2.5-coder:7b"

        def get_dialect_name(self, model):
            assert model == "qwen2.5-coder:7b"
            return "qwen"

    node = DefaultPromptStrategyNode(FakeModelSelector())

    model = node.select_model("lead_architect", "epic")
    dialect = node.select_dialect(model)

    assert model == "qwen2.5-coder:7b"
    assert dialect == "qwen"


def test_registry_resolves_default_router():
    registry = DecisionNodeRegistry()
    router = registry.resolve_router()
    assert isinstance(router, DefaultRouterNode)


def test_registry_resolves_custom_router():
    class CustomRouter(DefaultRouterNode):
        pass

    registry = DecisionNodeRegistry()
    custom = CustomRouter()
    registry.register_router("custom-router", custom)
    org = SimpleNamespace(process_rules={"router_node": "custom-router"})

    router = registry.resolve_router(org)

    assert router is custom


def test_registry_resolves_custom_prompt_strategy():
    class CustomPrompt:
        def select_model(self, role, asset_config):
            return "model-x"

        def select_dialect(self, model):
            return "generic"

    class FakeSelector:
        def select(self, role, asset_config):
            return "fallback"

        def get_dialect_name(self, model):
            return "fallback"

    registry = DecisionNodeRegistry()
    custom = CustomPrompt()
    registry.register_prompt_strategy("custom-prompt", custom)
    org = SimpleNamespace(process_rules={"prompt_strategy_node": "custom-prompt"})

    node = registry.resolve_prompt_strategy(FakeSelector(), org)
    assert node is custom


def test_default_evaluator_success_decisions():
    evaluator = DefaultEvaluatorNode()
    issue = _issue("I1", CardStatus.READY)
    updated_issue = _issue("I1", CardStatus.READY)
    turn = SimpleNamespace(content="Design decision captured.")

    result = evaluator.evaluate_success(
        issue=issue,
        updated_issue=updated_issue,
        turn=turn,
        seat_name="lead_architect",
        is_review_turn=False,
    )

    assert result["remember_decision"] is True
    assert result["trigger_sandbox"] is True
    assert result["promote_code_review"] is True


def test_default_evaluator_failure_governance_violation():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=1, max_retries=3)
    result = SimpleNamespace(violations=["blocked"])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "governance_violation"
    assert decision["next_retry_count"] == 1


def test_default_evaluator_failure_retry():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=1, max_retries=3)
    result = SimpleNamespace(violations=[])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "retry"
    assert decision["next_retry_count"] == 2


def test_default_evaluator_failure_catastrophic():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=3, max_retries=3)
    result = SimpleNamespace(violations=[])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "catastrophic"
    assert decision["next_retry_count"] == 4


def test_registry_resolves_custom_evaluator():
    class CustomEvaluator(DefaultEvaluatorNode):
        pass

    registry = DecisionNodeRegistry()
    custom = CustomEvaluator()
    registry.register_evaluator("custom-evaluator", custom)
    org = SimpleNamespace(process_rules={"evaluator_node": "custom-evaluator"})

    evaluator = registry.resolve_evaluator(org)

    assert evaluator is custom
