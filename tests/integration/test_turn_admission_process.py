"""Native owner death preserves all-or-none ordinary turn admission."""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.core.domain import AttemptState, RunState
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_recovery_transaction import INPUTS

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('boundary', ['before-commit', 'after-commit'])
# Layer: integration
async def test_native_admission_death_preserves_atomic_state_and_allows_identical_reentry(tmp_path, boundary):
    db = tmp_path / 'control_plane.sqlite3'
    service = build_turn_tool_control_plane_service(db)
    await service.execution_repository.get_run_record(run_id='initialize')
    await service.publication.repository.get_final_truth(run_id='initialize')
    before = await logical_state(db)
    supervisor = CommandProcessSupervisor(tmp_path, cancellation_event='test_admission_process_cancelled')
    task = asyncio.create_task(supervisor.run(
        [sys.executable, '-m', 'tests.helpers.turn_admission_worker', str(db), boundary],
        cwd=ROOT, environment={**os.environ, 'PYTHONPATH':str(ROOT), 'ORKET_DISABLE_SANDBOX':'1'}, timeout_seconds=45))
    files = AsyncFileTools(tmp_path)
    try:
        async with asyncio.timeout(30):
            while not await asyncio.to_thread((tmp_path / 'admission-ready.txt').exists):
                if task.done():
                    result = await task
                    pytest.fail(f'child exited {result.returncode}: {result.stderr!r}')
                await asyncio.sleep(0.02)
        visible = await logical_state(db)
        assert (visible == before) is (boundary == 'before-commit')
    finally:
        task.cancel()
        with pytest.raises(CommandProcessCancelled) as stopped:
            await asyncio.wait_for(task, timeout=15)
        assert stopped.value.lifetime.cleanup_confirmed
        await files.write_file('child.stdout.txt', stopped.value.lifetime.stdout.decode(errors='replace'))
        await files.write_file('child.stderr.txt', stopped.value.lifetime.stderr.decode(errors='replace'))
    assert await logical_state(db) == visible
    run, attempt = await asyncio.wait_for(service.begin_execution(**INPUTS, resume_mode=False), timeout=15)
    assert run.lifecycle_state is RunState.EXECUTING and attempt.attempt_state is AttemptState.EXECUTING
    assert run.current_attempt_id == attempt.attempt_id and attempt.run_id == run.run_id
    if boundary == 'after-commit':
        assert await logical_state(db) == visible
    assert not await service.execution_repository.list_step_records(attempt_id=attempt.attempt_id)
    assert not await service.publication.repository.list_effect_journal_entries(run_id=run.run_id)
