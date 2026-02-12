import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from types import SimpleNamespace
from orket.orchestration.orchestrator import Orchestrator
from orket.schema import EpicConfig, TeamConfig, EnvironmentConfig, CardStatus, IssueConfig
from orket.exceptions import CatastrophicFailure, ExecutionFailed

@pytest.fixture
def mock_cards():
    return AsyncMock()

@pytest.fixture
def mock_snapshots():
    return AsyncMock()

@pytest.fixture
def orchestrator(tmp_path, mock_cards, mock_snapshots):
    loader = MagicMock()
    sandbox = MagicMock()
    org = MagicMock()
    org.architecture.idesign_threshold = 10
    
    orch = Orchestrator(
        workspace=tmp_path,
        async_cards=mock_cards,
        snapshots=mock_snapshots,
        org=org,
        config_root=tmp_path,
        db_path="test.db",
        loader=loader,
        sandbox_orchestrator=sandbox
    )
    return orch

@pytest.mark.asyncio
async def test_execute_epic_completion(orchestrator, mock_cards):
    """Test that execute_epic exits when all issues are DONE."""
    epic = MagicMock(spec=EpicConfig)
    epic.name = "Test Epic"
    epic.issues = []
    epic.references = []
    
    mock_cards.get_by_build.return_value = [
        MagicMock(id="I1", status=CardStatus.DONE)
    ]
    mock_cards.get_independent_ready_issues.return_value = []
    
    # Mocking settings to avoid FileNotFoundError
    with patch("pathlib.Path.read_text", return_value='{"llm": {"provider": "ollama"}}'):
        await orchestrator.execute_epic(
            active_build="build-1",
            run_id="run-1",
            epic=epic,
            team=MagicMock(),
            env=MagicMock()
        )
    
    mock_cards.get_independent_ready_issues.assert_called()

@pytest.mark.asyncio
async def test_handle_failure_retry_limit(orchestrator, mock_cards):
    """Verify CatastrophicFailure on max retries."""
    issue = IssueConfig(
        id="I1", 
        seat="dev", 
        summary="Test", 
        retry_count=3, 
        max_retries=3
    )
    result = MagicMock()
    result.error = "Total failure"
    result.violations = []
    
    with patch("orket.state.runtime_state.get_task", return_value=AsyncMock()):
        with pytest.raises(CatastrophicFailure) as excinfo:
            await orchestrator._handle_failure(issue, result, "run-1", ["dev"])
            
    assert "MAX RETRIES EXCEEDED" in str(excinfo.value)
    mock_cards.update_status.assert_called_with("I1", CardStatus.BLOCKED)
    # Check that retry_count was incremented to 4
    args, _ = mock_cards.save.call_args
    assert args[0]["retry_count"] == 4

@pytest.mark.asyncio
async def test_handle_failure_retry_increment(orchestrator, mock_cards):
    """Verify status reset to READY and retry increment on partial failure."""
    issue = IssueConfig(
        id="I1", 
        seat="dev", 
        summary="Test", 
        retry_count=0, 
        max_retries=3
    )
    result = MagicMock()
    result.error = "Fixable error"
    result.violations = []
    
    with pytest.raises(ExecutionFailed):
        await orchestrator._handle_failure(issue, result, "run-1", ["dev"])
        
    mock_cards.update_status.assert_called_with("I1", CardStatus.READY)
    args, _ = mock_cards.save.call_args
    assert args[0]["retry_count"] == 1
    assert args[0]["status"] == CardStatus.READY


@pytest.mark.asyncio
async def test_handle_failure_uses_evaluator_exception_policy(orchestrator):
    issue = IssueConfig(
        id="I1",
        seat="dev",
        summary="Test",
        retry_count=0,
        max_retries=3,
    )
    result = MagicMock()
    result.error = "Fixable error"
    result.violations = []

    class CustomEvaluator:
        def evaluate_failure(self, issue, result):
            return {"action": "retry", "next_retry_count": issue.retry_count + 1}

        def failure_exception_class(self, action):
            return RuntimeError

        def status_for_failure_action(self, action):
            return CardStatus.READY

        def failure_event_name(self, action):
            return None

        def retry_failure_message(self, issue_id, retry_count, max_retries, error):
            return f"CUSTOM RETRY {issue_id} {retry_count}/{max_retries}: {error}"

    orchestrator.evaluator_node = CustomEvaluator()

    with pytest.raises(RuntimeError, match="CUSTOM RETRY I1 1/3: Fixable error"):
        await orchestrator._handle_failure(issue, result, "run-1", ["dev"])


@pytest.mark.asyncio
async def test_execute_epic_honors_custom_loop_policy(orchestrator, mock_cards):
    """Runtime seam test: custom loop policy controls execute_epic iteration behavior."""
    issue = MagicMock(id="I1", status=CardStatus.READY)
    epic = MagicMock(spec=EpicConfig)
    epic.name = "Policy Epic"
    epic.issues = [issue]
    epic.references = []

    mock_cards.get_by_build.return_value = [issue]
    mock_cards.get_independent_ready_issues.return_value = [issue]

    class CustomLoopPolicy:
        def concurrency_limit(self, organization):
            return 1

        def max_iterations(self, organization):
            return 1

        def is_backlog_done(self, backlog):
            return False

    orchestrator.loop_policy_node = CustomLoopPolicy()
    orchestrator._execute_issue_turn = AsyncMock(return_value=None)

    with pytest.raises(ExecutionFailed, match="Hyper-Loop exhausted iterations"):
        await orchestrator.execute_epic(
            active_build="build-policy",
            run_id="run-policy",
            epic=epic,
            team=MagicMock(),
            env=MagicMock(),
        )

    orchestrator._execute_issue_turn.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_epic_does_not_false_exhaust_on_iteration_boundary(orchestrator, mock_cards):
    """If the last allowed iteration completes work and backlog is then done, exhaustion should not raise."""
    ready_issue = MagicMock(id="I1", status=CardStatus.READY)
    done_issue = MagicMock(id="I1", status=CardStatus.DONE)

    epic = MagicMock(spec=EpicConfig)
    epic.name = "Boundary Epic"
    epic.issues = [ready_issue]
    epic.references = []

    mock_cards.get_by_build.side_effect = [[ready_issue], [done_issue]]
    mock_cards.get_independent_ready_issues.return_value = [ready_issue]

    class CustomLoopPolicy:
        def concurrency_limit(self, organization):
            return 1

        def max_iterations(self, organization):
            return 1

        def is_backlog_done(self, backlog):
            return all(i.status == CardStatus.DONE for i in backlog)

    orchestrator.loop_policy_node = CustomLoopPolicy()
    orchestrator._execute_issue_turn = AsyncMock(return_value=None)

    with patch("pathlib.Path.read_text", return_value='{"llm": {"provider": "ollama"}}'):
        await orchestrator.execute_epic(
            active_build="build-boundary",
            run_id="run-boundary",
            epic=epic,
            team=MagicMock(),
            env=MagicMock(),
        )

    orchestrator._execute_issue_turn.assert_awaited_once()


@pytest.mark.asyncio
async def test_execute_issue_turn_uses_custom_model_client_node(orchestrator, mock_cards, monkeypatch):
    issue = IssueConfig(id="I1", seat="dev", summary="Test")
    issue_data = SimpleNamespace(model_dump=lambda: issue.model_dump())
    epic = SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1")
    team = SimpleNamespace(seats={"dev": SimpleNamespace(roles=["lead_architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    orchestrator.loader.load_asset.side_effect = [
        SimpleNamespace(name="dev", description="role", tools=[]),  # RoleConfig
        SimpleNamespace(model_family="generic", dsl_format="json", constraints=[], hallucination_guard="none"),  # DialectConfig
    ]
    orchestrator.memory.search = AsyncMock(return_value=[])
    orchestrator.memory.remember = AsyncMock()
    orchestrator._save_checkpoint = AsyncMock()
    orchestrator._trigger_sandbox = AsyncMock()
    mock_cards.get_by_id.return_value = SimpleNamespace(status=CardStatus.DONE)

    class CustomModelClientNode:
        def __init__(self):
            self.provider_calls = 0
            self.client_calls = 0

        def create_provider(self, selected_model, env):
            self.provider_calls += 1

            class FakeProvider:
                async def clear_context(self):
                    return None

            return FakeProvider()

        def create_client(self, provider):
            self.client_calls += 1

            class FakeClient:
                async def complete(self, messages):
                    return SimpleNamespace(content="ok", raw={})

            return FakeClient()

    custom_node = CustomModelClientNode()
    orchestrator.model_client_node = custom_node

    prompt_strategy_node = SimpleNamespace(
        select_model=lambda role, asset_config: "dummy-model",
        select_dialect=lambda model: "generic",
    )
    executor = SimpleNamespace(
        execute_turn=AsyncMock(
            return_value=SimpleNamespace(
                success=True,
                turn=SimpleNamespace(content="done", role="dev", issue_id="I1", note=""),
            )
        )
    )

    monkeypatch.setattr("orket.orchestration.orchestrator.PromptCompiler.compile", lambda skill, dialect: "SYSTEM")

    await orchestrator._execute_issue_turn(
        issue_data=issue_data,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=prompt_strategy_node,
        executor=executor,
        toolbox=MagicMock(),
    )

    assert custom_node.provider_calls == 1
    assert custom_node.client_calls == 1


@pytest.mark.asyncio
async def test_execute_epic_uses_custom_tool_strategy_node(tmp_path):
    """Execution-path seam test: execute_epic builds ToolBox from orchestrator registry and uses custom tool strategy."""
    from orket.schema import CardStatus
    from orket.orchestration.turn_executor import TurnResult

    issue_ready = SimpleNamespace(id="I1", status=CardStatus.READY, seat="lead_architect", model_dump=lambda: {"id": "I1", "seat": "lead_architect", "summary": "Test", "status": "ready"})
    issue_done = SimpleNamespace(id="I1", status=CardStatus.DONE, seat="lead_architect")

    async_cards = AsyncMock()
    async_cards.get_by_build = AsyncMock(side_effect=[[issue_ready], [issue_done]])
    async_cards.get_independent_ready_issues = AsyncMock(side_effect=[[issue_ready], []])
    async_cards.get_by_id = AsyncMock(return_value=SimpleNamespace(status=CardStatus.DONE))
    async_cards.update_status = AsyncMock()

    snapshots = AsyncMock()
    loader = MagicMock()
    sandbox = MagicMock()

    org = SimpleNamespace(process_rules={"tool_strategy_node": "custom-tool-strategy"})
    orch = Orchestrator(
        workspace=tmp_path,
        async_cards=async_cards,
        snapshots=snapshots,
        org=org,
        config_root=tmp_path,
        db_path="test.db",
        loader=loader,
        sandbox_orchestrator=sandbox,
    )

    class CustomToolStrategy:
        def compose(self, toolbox):
            return {
                "custom_noop": lambda args, context=None: {"ok": True, "tool": "custom_noop", "args": args},
            }

    orch.decision_nodes.register_tool_strategy("custom-tool-strategy", CustomToolStrategy())

    epic = SimpleNamespace(name="Tool Strategy Epic", references=[], issues=[], parent_id=None, id="EPIC-1")
    team = SimpleNamespace(seats={"lead_architect": SimpleNamespace(roles=["lead_architect"])})
    env = SimpleNamespace(temperature=0.1, timeout=30)

    loader.load_asset.side_effect = [
        SimpleNamespace(name="lead_architect", description="Role", tools=["custom_noop"]),
        SimpleNamespace(model_family="generic", dsl_format="json", constraints=[], hallucination_guard="none"),
    ]

    class FakeModelClientNode:
        def create_provider(self, selected_model, env):
            class P:
                async def clear_context(self):
                    return None
            return P()

        def create_client(self, provider):
            class C:
                async def complete(self, messages):
                    return SimpleNamespace(content="ok", raw={})
            return C()

    orch.model_client_node = FakeModelClientNode()
    orch.memory.search = AsyncMock(return_value=[])
    orch.memory.remember = AsyncMock()
    orch._save_checkpoint = AsyncMock()

    class FakePromptStrategy:
        def select_model(self, role, asset_config):
            return "dummy-model"

        def select_dialect(self, model):
            return "generic"

    orch.decision_nodes.resolve_prompt_strategy = MagicMock(return_value=FakePromptStrategy())

    tool_strategy_hit = {"used": False}

    async def fake_execute_turn(self, issue, role_config, client, toolbox, context, system_prompt):
        res = await toolbox.execute("custom_noop", {"x": 1}, context=context)
        tool_strategy_hit["used"] = res.get("ok") is True and res.get("tool") == "custom_noop"
        return TurnResult(
            success=True,
            turn=SimpleNamespace(role=context["role"], issue_id=context["issue_id"], content="done", note=""),
        )

    with patch("orket.orchestration.orchestrator.TurnExecutor.execute_turn", new=fake_execute_turn):
        await orch.execute_epic(
            active_build="build-tool-strategy",
            run_id="run-tool-strategy",
            epic=epic,
            team=team,
            env=env,
        )

    assert tool_strategy_hit["used"] is True
