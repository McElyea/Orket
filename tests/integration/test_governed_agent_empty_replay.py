from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority

pytestmark = pytest.mark.integration


# Layer: integration
async def test_existing_run_without_decisions_does_not_claim_replay_match(tmp_path: Path) -> None:
    path = tmp_path / "agent.sqlite3"
    request = agent_request()
    seed = tmp_path / "seed.sqlite3"
    await prepare_authority(seed, request, binding_for(request))
    record = await AsyncControlPlaneExecutionRepository(seed).get_run_record(run_id="run-1")
    await AsyncControlPlaneExecutionRepository(path).save_run_record(
        record=record.model_copy(update={"current_attempt_id": None, "state_revision": None})
    )
    repository = AsyncGovernedAgentRepository(path)
    inspector = GovernedAgentInspectionService(
        replay_repository=GovernedAgentReplayStore(path),
        iteration_repository=repository,
        call_repository=repository,
    )
    assert await inspector.replay(run_id="missing") is None
    replay = await inspector.replay(run_id="run-1")
    assert replay["status"] == "no_decisions"
    assert replay["decisions"] == []
    assert replay["expected_count"] == replay["compared_count"] == 0
    assert replay["full_execution_verified"] is False
