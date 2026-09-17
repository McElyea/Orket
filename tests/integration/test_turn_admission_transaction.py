"""Counterexample for the remaining BT-5 ordinary-turn admission transaction."""
import asyncio

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_recovery_transaction import INPUTS

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures('deterministic_turn_clock')]
WRITES = [('save_resolved_policy_snapshot', 1), ('save_resolved_configuration_snapshot', 1),
          ('save_run_record', 1), ('save_run_record', 2), ('save_run_record', 3),
          ('save_attempt_record', 1), ('save_attempt_record', 2),
          ('save_reservation_record', 1), ('save_reservation_record', 2),
          ('append_lease_record', 1), ('save_resource_record', 1)]


@pytest.mark.parametrize('method,ordinal', WRITES)
@pytest.mark.parametrize('cancel', [False, True], ids=['error','cancel'])
# Layer: integration
async def test_turn_admission_interruption_does_not_leave_partial_authority(tmp_path, monkeypatch, method, ordinal, cancel):
    service = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    await service.execution_repository.get_run_record(run_id='initialize')
    await service.publication.repository.get_final_truth(run_id='initialize')
    before = await logical_state(service.execution_repository.db_path)
    owner = AsyncControlPlaneExecutionRepository if method in {'save_run_record','save_attempt_record'} else AsyncControlPlaneRecordRepository
    original = getattr(owner, method)
    calls = 0

    async def interrupted(repository, **kwargs):
        nonlocal calls
        result = await original(repository, **kwargs)
        calls += 1
        if calls != ordinal:
            return result
        if cancel:
            raise asyncio.CancelledError('ordinary turn admission write interrupted')
        raise RuntimeError('ordinary turn admission write interrupted')

    monkeypatch.setattr(owner, method, interrupted)
    task = asyncio.create_task(service.begin_execution(**INPUTS, resume_mode=False))
    with pytest.raises(asyncio.CancelledError if cancel else RuntimeError):
        await task
    assert task.done()
    assert calls >= ordinal
    assert await logical_state(service.execution_repository.db_path) == before


# Layer: integration
async def test_healthy_turn_admission_has_current_executing_attempt(tmp_path):
    service = build_turn_tool_control_plane_service(tmp_path / 'control_plane.sqlite3')
    run, attempt = await service.begin_execution(**INPUTS, resume_mode=False)
    assert run.current_attempt_id == attempt.attempt_id and attempt.run_id == run.run_id
    assert run.lifecycle_state.value == 'executing' and attempt.attempt_state.value == 'attempt_executing'
