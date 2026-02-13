from datetime import datetime, UTC
from types import SimpleNamespace
from pathlib import Path

from orket.decision_nodes.builtins import (
    DefaultApiRuntimeStrategyNode,
    DefaultEvaluatorNode,
    DefaultPlannerNode,
    DefaultPromptStrategyNode,
    DefaultRouterNode,
)
from orket.decision_nodes.contracts import PlanningInput
from orket.decision_nodes.registry import DecisionNodeRegistry
from orket.exceptions import CatastrophicFailure, ExecutionFailed, GovernanceViolation
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
    assert evaluator.success_post_actions(result) == {
        "trigger_sandbox": True,
        "next_status": CardStatus.CODE_REVIEW,
    }
    actions = evaluator.success_post_actions(result)
    assert evaluator.should_trigger_sandbox(actions) is True
    assert evaluator.next_status_after_success(actions) == CardStatus.CODE_REVIEW


def test_default_evaluator_failure_governance_violation():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=1, max_retries=3)
    result = SimpleNamespace(violations=["blocked"])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "governance_violation"
    assert decision["next_retry_count"] == 1
    assert evaluator.status_for_failure_action(decision["action"]) == CardStatus.BLOCKED
    assert evaluator.should_cancel_session(decision["action"]) is False
    assert evaluator.failure_event_name(decision["action"]) is None
    assert evaluator.governance_violation_message("blocked") == "iDesign Violation: blocked"


def test_default_evaluator_failure_retry():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=1, max_retries=3)
    result = SimpleNamespace(violations=[])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "retry"
    assert decision["next_retry_count"] == 2
    assert evaluator.status_for_failure_action(decision["action"]) == CardStatus.READY
    assert evaluator.should_cancel_session(decision["action"]) is False
    assert evaluator.failure_event_name(decision["action"]) == "retry_triggered"
    assert evaluator.retry_failure_message("I1", 2, 3, "oops") == "Orchestration Turn Failed (Retry 2/3): oops"


def test_default_evaluator_failure_catastrophic():
    evaluator = DefaultEvaluatorNode()
    issue = SimpleNamespace(retry_count=3, max_retries=3)
    result = SimpleNamespace(violations=[])

    decision = evaluator.evaluate_failure(issue, result)

    assert decision["action"] == "catastrophic"
    assert decision["next_retry_count"] == 4
    assert evaluator.status_for_failure_action(decision["action"]) == CardStatus.BLOCKED
    assert evaluator.should_cancel_session(decision["action"]) is True
    assert evaluator.failure_event_name(decision["action"]) == "catastrophic_failure"
    assert evaluator.catastrophic_failure_message("I1", 3) == (
        "MAX RETRIES EXCEEDED for I1. Limit: 3. Shutting down project orchestration."
    )
    assert evaluator.unexpected_failure_action_message("weird", "I1") == "Unexpected evaluator action 'weird' for I1"


def test_default_evaluator_failure_exception_class_mapping():
    evaluator = DefaultEvaluatorNode()
    assert evaluator.failure_exception_class("governance_violation") is GovernanceViolation
    assert evaluator.failure_exception_class("catastrophic") is CatastrophicFailure
    assert evaluator.failure_exception_class("retry") is ExecutionFailed
    assert evaluator.failure_exception_class("unknown") is ExecutionFailed


def test_registry_resolves_custom_evaluator():
    class CustomEvaluator(DefaultEvaluatorNode):
        pass

    registry = DecisionNodeRegistry()
    custom = CustomEvaluator()
    registry.register_evaluator("custom-evaluator", custom)
    org = SimpleNamespace(process_rules={"evaluator_node": "custom-evaluator"})

    evaluator = registry.resolve_evaluator(org)

    assert evaluator is custom


def test_registry_resolves_default_tool_strategy():
    registry = DecisionNodeRegistry()

    node = registry.resolve_tool_strategy()

    from orket.decision_nodes.builtins import DefaultToolStrategyNode

    assert isinstance(node, DefaultToolStrategyNode)


def test_registry_resolves_custom_tool_strategy_from_process_rules(monkeypatch):
    class CustomToolStrategy:
        def compose(self, toolbox):
            return {"custom": lambda *_args, **_kwargs: {"ok": True}}

    monkeypatch.delenv("ORKET_TOOL_STRATEGY_NODE", raising=False)

    registry = DecisionNodeRegistry()
    custom = CustomToolStrategy()
    registry.register_tool_strategy("custom-tools", custom)
    org = SimpleNamespace(process_rules={"tool_strategy_node": "custom-tools"})

    node = registry.resolve_tool_strategy(org)

    assert node is custom


def test_registry_tool_strategy_env_override_wins(monkeypatch):
    class CustomToolStrategy:
        def compose(self, toolbox):
            return {"custom": lambda *_args, **_kwargs: {"ok": True}}

    monkeypatch.setenv("ORKET_TOOL_STRATEGY_NODE", "custom-tools")

    registry = DecisionNodeRegistry()
    custom = CustomToolStrategy()
    registry.register_tool_strategy("custom-tools", custom)
    org = SimpleNamespace(process_rules={"tool_strategy_node": "default"})

    node = registry.resolve_tool_strategy(org)

    assert node is custom


def test_default_api_runtime_strategy_parity(monkeypatch):
    node = DefaultApiRuntimeStrategyNode()

    assert node.default_allowed_origins_value() == "http://localhost:5173,http://127.0.0.1:5173"
    assert node.parse_allowed_origins("http://a, http://b") == ["http://a", "http://b"]
    monkeypatch.delenv("ORKET_ALLOW_INSECURE_NO_API_KEY", raising=False)
    assert node.is_api_key_valid(None, None) is False
    monkeypatch.setenv("ORKET_ALLOW_INSECURE_NO_API_KEY", "true")
    assert node.is_api_key_valid(None, None) is True
    assert node.is_api_key_valid("k", "k") is True
    assert node.is_api_key_valid("k", "x") is False
    assert node.api_key_invalid_detail() == "Could not validate credentials"
    assert node.resolve_asset_id(path="model/core/issues/demo.json", issue_id=None) == "demo"
    assert node.resolve_asset_id(path=None, issue_id="ISSUE-1") == "ISSUE-1"
    assert node.resolve_asset_id(path=None, issue_id=None) is None
    assert len(node.create_session_id()) == 8
    assert node.resolve_run_active_invocation(
        asset_id="ISSUE-1",
        build_id="BUILD-1",
        session_id="SESSION-1",
        request_type="issue",
    ) == {
        "method_name": "run_card",
        "kwargs": {
            "card_id": "ISSUE-1",
            "build_id": "BUILD-1",
            "session_id": "SESSION-1",
        },
    }
    assert node.run_active_missing_asset_detail() == "No asset ID provided."
    assert node.resolve_runs_invocation() == {"method_name": "get_recent_runs", "args": []}
    assert node.resolve_backlog_invocation("SESS-1") == {
        "method_name": "get_session_issues",
        "args": ["SESS-1"],
    }
    assert node.resolve_session_detail_invocation("SESS-1") == {
        "method_name": "get_session",
        "args": ["SESS-1"],
    }
    assert node.session_detail_not_found_error("SESS-1") == {"status_code": 404}
    assert node.resolve_session_snapshot_invocation("SESS-1") == {
        "method_name": "get",
        "args": ["SESS-1"],
    }
    assert node.session_snapshot_not_found_error("SESS-1") == {"status_code": 404}
    assert node.resolve_sandboxes_list_invocation() == {"method_name": "get_sandboxes", "args": []}
    assert node.resolve_sandbox_stop_invocation("sb-1") == {
        "method_name": "stop_sandbox",
        "args": ["sb-1"],
    }
    assert node.resolve_clear_logs_path() == "workspace/default/orket.log"
    assert node.resolve_clear_logs_invocation("workspace/default/orket.log") == {
        "method_name": "write_file",
        "args": ["workspace/default/orket.log", ""],
    }
    assert node.resolve_read_invocation("x.txt") == {"method_name": "read_file", "args": ["x.txt"]}
    assert node.read_not_found_detail("x.txt") == "File not found"
    assert node.permission_denied_detail("read", "denied") == "denied"
    assert node.resolve_save_invocation("x.txt", "hello") == {
        "method_name": "write_file",
        "args": ["x.txt", "hello"],
    }
    assert node.normalize_metrics({"cpu_percent": 12, "ram_percent": 34}) == {
        "cpu_percent": 12,
        "ram_percent": 34,
        "cpu": 12,
        "memory": 34,
    }
    assert node.calendar_window(datetime(2026, 2, 11, tzinfo=UTC)) == {
        "sprint_start": "2026-02-09",
        "sprint_end": "2026-02-13",
    }
    assert node.resolve_current_sprint(datetime(2026, 2, 11, tzinfo=UTC)) == "Q1 S7"
    assert node.resolve_explorer_path(Path("/tmp/root"), "../../evil") is None
    assert node.resolve_explorer_forbidden_error("../../evil") == {"status_code": 403}
    assert node.resolve_explorer_missing_response("missing") == {"items": [], "path": "missing"}
    assert node.include_explorer_entry(".git") is False
    assert node.include_explorer_entry("node_modules") is False
    assert node.include_explorer_entry("app.py") is True
    assert node.sort_explorer_items(
        [{"name": "z.txt", "is_dir": False}, {"name": "A", "is_dir": True}]
    ) == [{"name": "A", "is_dir": True}, {"name": "z.txt", "is_dir": False}]
    assert node.resolve_preview_target("model/core/rocks/demo.json", None) == {
        "mode": "rock",
        "asset_name": "demo",
        "department": "core",
    }
    assert node.resolve_preview_target("model/product/epics/my_epic.json", "ISSUE-1") == {
        "mode": "issue",
        "asset_name": "my_epic",
        "department": "product",
    }
    assert node.select_preview_build_method("issue") == "build_issue_preview"
    assert node.select_preview_build_method("rock") == "build_rock_preview"
    assert node.select_preview_build_method("epic") == "build_epic_preview"
    assert node.resolve_preview_invocation(
        {"mode": "issue", "asset_name": "my_epic", "department": "product"},
        "ISSUE-1",
    ) == {
        "method_name": "build_issue_preview",
        "args": ["ISSUE-1", "my_epic", "product"],
        "unsupported_detail": "Unsupported preview mode 'issue'.",
    }
    assert node.preview_unsupported_detail(
        {"mode": "custom", "asset_name": "x", "department": "core"},
        {"method_name": "build_custom_preview", "args": []},
    ) == "Unsupported preview mode 'custom'."
    assert node.resolve_chat_driver_invocation("hello") == {
        "method_name": "process_request",
        "args": ["hello"],
    }
    assert node.resolve_member_metrics_workspace(Path("/tmp/root"), "missing") == Path("/tmp/root/workspace/default")
    assert callable(node.create_member_metrics_reader())
    assert node.resolve_sandbox_workspace(Path("/tmp/root")) == Path("/tmp/root/workspace/default")
    assert node.resolve_sandbox_logs_invocation("sb-1", "api") == {
        "method_name": "get_logs",
        "args": ["sb-1", "api"],
    }
    assert node.resolve_api_workspace(Path("/tmp/root")) == Path("/tmp/root/workspace/default")
    assert node.should_remove_websocket(RuntimeError("x")) is True
    assert node.should_remove_websocket(ValueError("x")) is True
    assert node.should_remove_websocket(Exception("x")) is False


def test_registry_resolves_custom_api_runtime_from_process_rules(monkeypatch):
    class CustomApiRuntime:
        def parse_allowed_origins(self, origins_value):
            return ["http://custom"]

        def resolve_asset_id(self, path, issue_id):
            return "X"

        def create_session_id(self):
            return "SESSIONX"

    monkeypatch.delenv("ORKET_API_RUNTIME_NODE", raising=False)

    registry = DecisionNodeRegistry()
    custom = CustomApiRuntime()
    registry.register_api_runtime("custom-api", custom)
    org = SimpleNamespace(process_rules={"api_runtime_node": "custom-api"})

    node = registry.resolve_api_runtime(org)

    assert node is custom


def test_registry_api_runtime_env_override_wins(monkeypatch):
    class CustomApiRuntime:
        def parse_allowed_origins(self, origins_value):
            return ["http://custom"]

        def resolve_asset_id(self, path, issue_id):
            return "X"

        def create_session_id(self):
            return "SESSIONX"

    monkeypatch.setenv("ORKET_API_RUNTIME_NODE", "custom-api")

    registry = DecisionNodeRegistry()
    custom = CustomApiRuntime()
    registry.register_api_runtime("custom-api", custom)
    org = SimpleNamespace(process_rules={"api_runtime_node": "default"})

    node = registry.resolve_api_runtime(org)

    assert node is custom


def test_registry_resolves_default_sandbox_policy():
    registry = DecisionNodeRegistry()
    node = registry.resolve_sandbox_policy()
    from orket.decision_nodes.builtins import DefaultSandboxPolicyNode
    assert isinstance(node, DefaultSandboxPolicyNode)


def test_registry_resolves_custom_sandbox_policy(monkeypatch):
    class CustomSandboxPolicy:
        def build_sandbox_id(self, rock_id):
            return "sandbox-custom"

        def build_compose_project(self, sandbox_id):
            return "orket-custom"

        def get_database_url(self, tech_stack, ports, db_password=""):
            return "db://custom"

        def generate_compose_file(self, sandbox, db_password, admin_password):
            return "version: '3.8'"

    monkeypatch.delenv("ORKET_SANDBOX_POLICY_NODE", raising=False)
    registry = DecisionNodeRegistry()
    custom = CustomSandboxPolicy()
    registry.register_sandbox_policy("custom-sandbox", custom)
    org = SimpleNamespace(process_rules={"sandbox_policy_node": "custom-sandbox"})
    assert registry.resolve_sandbox_policy(org) is custom


def test_registry_sandbox_policy_env_override_wins(monkeypatch):
    class CustomSandboxPolicy:
        def build_sandbox_id(self, rock_id):
            return "sandbox-custom"

        def build_compose_project(self, sandbox_id):
            return "orket-custom"

        def get_database_url(self, tech_stack, ports, db_password=""):
            return "db://custom"

        def generate_compose_file(self, sandbox, db_password, admin_password):
            return "version: '3.8'"

    monkeypatch.setenv("ORKET_SANDBOX_POLICY_NODE", "custom-sandbox")
    registry = DecisionNodeRegistry()
    custom = CustomSandboxPolicy()
    registry.register_sandbox_policy("custom-sandbox", custom)
    org = SimpleNamespace(process_rules={"sandbox_policy_node": "default"})
    assert registry.resolve_sandbox_policy(org) is custom


def test_registry_resolves_default_engine_runtime():
    registry = DecisionNodeRegistry()
    node = registry.resolve_engine_runtime()
    from orket.decision_nodes.builtins import DefaultEngineRuntimePolicyNode
    assert isinstance(node, DefaultEngineRuntimePolicyNode)


def test_registry_engine_runtime_env_override_wins(monkeypatch):
    class CustomEngineRuntime:
        def bootstrap_environment(self):
            return None

        def resolve_config_root(self, config_root):
            return config_root

    monkeypatch.setenv("ORKET_ENGINE_RUNTIME_NODE", "custom-engine")
    registry = DecisionNodeRegistry()
    custom = CustomEngineRuntime()
    registry.register_engine_runtime("custom-engine", custom)
    org = SimpleNamespace(process_rules={"engine_runtime_node": "default"})
    assert registry.resolve_engine_runtime(org) is custom


def test_registry_resolves_default_loader_strategy():
    registry = DecisionNodeRegistry()
    from orket.decision_nodes.builtins import DefaultLoaderStrategyNode
    assert isinstance(registry.resolve_loader_strategy(), DefaultLoaderStrategyNode)


def test_registry_loader_strategy_env_override_wins(monkeypatch):
    class CustomLoaderStrategy:
        def organization_modular_paths(self, config_dir):
            return (config_dir / "a.json", config_dir / "b.json")

        def organization_fallback_paths(self, config_dir, model_dir):
            return [config_dir / "organization.json"]

        def department_paths(self, config_dir, model_dir, name):
            return [config_dir / f"{name}.json"]

        def asset_paths(self, config_dir, model_dir, dept, category, name):
            return [config_dir / category / f"{name}.json"]

        def list_asset_search_paths(self, config_dir, model_dir, dept, category):
            return [config_dir / category]

        def apply_organization_overrides(self, org, get_setting):
            return org

    monkeypatch.setenv("ORKET_LOADER_STRATEGY_NODE", "custom-loader")
    registry = DecisionNodeRegistry()
    custom = CustomLoaderStrategy()
    registry.register_loader_strategy("custom-loader", custom)
    org = SimpleNamespace(process_rules={"loader_strategy_node": "default"})
    assert registry.resolve_loader_strategy(org) is custom


def test_registry_resolves_default_execution_runtime():
    registry = DecisionNodeRegistry()
    from orket.decision_nodes.builtins import DefaultExecutionRuntimeStrategyNode
    node = registry.resolve_execution_runtime()
    assert isinstance(node, DefaultExecutionRuntimeStrategyNode)
    assert len(node.select_run_id(None)) == 8
    assert node.select_epic_build_id(None, "My Epic", lambda s: s.lower().replace(" ", "-")) == "build-my-epic"


def test_registry_execution_runtime_env_override_wins(monkeypatch):
    class CustomExecutionRuntime:
        def select_run_id(self, session_id):
            return "RUNX"

        def select_epic_build_id(self, build_id, epic_name, sanitize_name):
            return "BUILDX"

        def select_rock_session_id(self, session_id):
            return "ROCKRUNX"

        def select_rock_build_id(self, build_id, rock_name, sanitize_name):
            return "ROCKBUILDX"

    monkeypatch.setenv("ORKET_EXECUTION_RUNTIME_NODE", "custom-runtime")
    registry = DecisionNodeRegistry()
    custom = CustomExecutionRuntime()
    registry.register_execution_runtime("custom-runtime", custom)
    org = SimpleNamespace(process_rules={"execution_runtime_node": "default"})
    assert registry.resolve_execution_runtime(org) is custom


def test_registry_resolves_default_pipeline_wiring():
    registry = DecisionNodeRegistry()
    from orket.decision_nodes.builtins import DefaultPipelineWiringStrategyNode
    assert isinstance(registry.resolve_pipeline_wiring(), DefaultPipelineWiringStrategyNode)


def test_registry_pipeline_wiring_env_override_wins(monkeypatch):
    class CustomPipelineWiring:
        def create_sandbox_orchestrator(self, workspace, organization):
            return object()

        def create_webhook_database(self):
            return object()

        def create_bug_fix_manager(self, organization, webhook_db):
            return object()

        def create_orchestrator(self, workspace, async_cards, snapshots, org, config_root, db_path, loader, sandbox_orchestrator):
            return object()

        def create_sub_pipeline(self, parent_pipeline, epic_workspace, department):
            return object()

    monkeypatch.setenv("ORKET_PIPELINE_WIRING_NODE", "custom-pipeline")
    registry = DecisionNodeRegistry()
    custom = CustomPipelineWiring()
    registry.register_pipeline_wiring("custom-pipeline", custom)
    org = SimpleNamespace(process_rules={"pipeline_wiring_node": "default"})
    assert registry.resolve_pipeline_wiring(org) is custom


def test_registry_resolves_default_orchestration_loop_policy():
    registry = DecisionNodeRegistry()
    from orket.decision_nodes.builtins import DefaultOrchestrationLoopPolicyNode
    node = registry.resolve_orchestration_loop()
    assert isinstance(node, DefaultOrchestrationLoopPolicyNode)
    assert node.context_window(None) == 10
    assert node.is_review_turn(CardStatus.CODE_REVIEW) is True
    assert node.is_review_turn(CardStatus.READY) is False
    assert node.turn_status_for_issue(True) == CardStatus.CODE_REVIEW
    assert node.turn_status_for_issue(False) == CardStatus.IN_PROGRESS
    assert node.role_order_for_turn(["coder"], is_review_turn=False) == ["coder"]
    assert node.role_order_for_turn(["coder"], is_review_turn=True) == ["integrity_guard", "coder"]
    assert node.missing_seat_status() == CardStatus.CANCELED
    assert node.no_candidate_outcome([SimpleNamespace(status=CardStatus.DONE)]) == {
        "is_done": True,
        "event_name": "orchestrator_epic_complete",
    }
    assert node.no_candidate_outcome([SimpleNamespace(status=CardStatus.ARCHIVED)]) == {
        "is_done": True,
        "event_name": "orchestrator_epic_complete",
    }
    assert node.no_candidate_outcome([SimpleNamespace(status=CardStatus.READY)]) == {
        "is_done": False,
        "event_name": None,
    }
    assert node.should_raise_exhaustion(20, 20, [SimpleNamespace(status=CardStatus.READY)]) is True
    assert node.should_raise_exhaustion(20, 20, [SimpleNamespace(status=CardStatus.DONE)]) is False


def test_registry_orchestration_loop_env_override_wins(monkeypatch):
    class CustomLoop:
        def concurrency_limit(self, organization):
            return 1

        def max_iterations(self, organization):
            return 5

        def is_backlog_done(self, backlog):
            return False

    monkeypatch.setenv("ORKET_ORCHESTRATION_LOOP_NODE", "custom-loop")
    registry = DecisionNodeRegistry()
    custom = CustomLoop()
    registry.register_orchestration_loop("custom-loop", custom)
    org = SimpleNamespace(process_rules={"orchestration_loop_node": "default"})
    assert registry.resolve_orchestration_loop(org) is custom


def test_default_orchestration_loop_context_window_env_override(monkeypatch):
    from orket.decision_nodes.builtins import DefaultOrchestrationLoopPolicyNode

    monkeypatch.setenv("ORKET_CONTEXT_WINDOW", "3")
    node = DefaultOrchestrationLoopPolicyNode()
    assert node.context_window(None) == 3

    monkeypatch.setenv("ORKET_CONTEXT_WINDOW", "bad")
    assert node.context_window(None) == 10


def test_registry_resolves_default_model_client_policy():
    registry = DecisionNodeRegistry()
    from orket.decision_nodes.builtins import DefaultModelClientPolicyNode
    assert isinstance(registry.resolve_model_client(), DefaultModelClientPolicyNode)


def test_registry_model_client_env_override_wins(monkeypatch):
    class CustomModelClient:
        def create_provider(self, selected_model, env):
            return object()

        def create_client(self, provider):
            return object()

    monkeypatch.setenv("ORKET_MODEL_CLIENT_NODE", "custom-model-client")
    registry = DecisionNodeRegistry()
    custom = CustomModelClient()
    registry.register_model_client("custom-model-client", custom)
    org = SimpleNamespace(process_rules={"model_client_node": "default"})
    assert registry.resolve_model_client(org) is custom

