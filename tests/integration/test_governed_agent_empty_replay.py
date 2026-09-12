from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority

pytestmark = pytest.mark.integration


async def test_existing_run_without_decisions_does_not_claim_replay_match(tmp_path: Path) -> None:
    path = tmp_path / "agent.sqlite3"
    request = agent_request()
    seed = tmp_path / "seed.sqlite3"
    await prepare_authority(seed, request, binding_for(request))
    record = await AsyncControlPlaneExecutionRepository(seed).get_run_record(run_id="run-1")
    await AsyncControlPlaneExecutionRepository(path).save_run_record(record=record)
    repository = AsyncGovernedAgentRepository(path)
    inspector = GovernedAgentInspectionService(
        execution_repository=AsyncControlPlaneExecutionRepository(path),
        iteration_repository=repository,
        call_repository=repository,
        truth_repository=AsyncControlPlaneRecordRepository(path),
    )
    assert await inspector.replay(run_id="missing") is None
    replay = await inspector.replay(run_id="run-1")
    assert replay["status"] == "no_decisions"
    assert replay["decisions"] == []
