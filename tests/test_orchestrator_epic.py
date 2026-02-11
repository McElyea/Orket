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
