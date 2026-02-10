import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from orket.orchestration.engine import OrchestrationEngine

@pytest.mark.asyncio
async def test_engine_explicit_calls():
    # Mock workspace
    workspace = Path("./test_workspace")
    
    # Mock OrchestrationEngine and its pipeline
    with pytest.MonkeyPatch().context() as mp:
        # Mock load_env to prevent searching for .env
        mp.setattr("orket.settings.load_env", lambda: None)
        
        # Mock repositories to prevent DB connection
        mp.setattr("orket.infrastructure.async_card_repository.AsyncCardRepository._ensure_initialized", AsyncMock())
        mp.setattr("orket.infrastructure.sqlite_repositories.SQLiteSessionRepository", MagicMock())
        mp.setattr("orket.infrastructure.sqlite_repositories.SQLiteSnapshotRepository", MagicMock())
        
        # Mock ExecutionPipeline
        mock_pipeline = AsyncMock()
        mp.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: mock_pipeline)
        
        engine = OrchestrationEngine(workspace)
        
        # 1. Test run_epic
        await engine.run_epic("my-epic")
        mock_pipeline.run_epic.assert_called_once_with(
            "my-epic",
            build_id=None,
            session_id=None,
            driver_steered=False
        )
        
        # 2. Test run_rock
        await engine.run_rock("my-rock")
        mock_pipeline.run_rock.assert_called_once_with(
            "my-rock",
            build_id=None,
            session_id=None,
            driver_steered=False
        )
        
        # 3. Test run_issue
        await engine.run_issue("my-issue")
        mock_pipeline.run_card.assert_called_with(
            "my-issue",
            build_id=None,
            session_id=None,
            driver_steered=False
        )

@pytest.mark.asyncio
async def test_engine_run_card_deprecated():
    # Mock workspace
    workspace = Path("./test_workspace")
    
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("orket.settings.load_env", lambda: None)
        mp.setattr("orket.infrastructure.async_card_repository.AsyncCardRepository._ensure_initialized", AsyncMock())
        mp.setattr("orket.infrastructure.sqlite_repositories.SQLiteSessionRepository", MagicMock())
        mp.setattr("orket.infrastructure.sqlite_repositories.SQLiteSnapshotRepository", MagicMock())
        
        mock_pipeline = AsyncMock()
        mp.setattr("orket.orket.ExecutionPipeline", lambda *args, **kwargs: mock_pipeline)
        
        engine = OrchestrationEngine(workspace)
        
        await engine.run_card("some-card", target_issue_id="I1")
        mock_pipeline.run_card.assert_called_once_with(
            "some-card",
            build_id=None,
            session_id=None,
            driver_steered=False,
            target_issue_id="I1"
        )
