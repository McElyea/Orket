"""Native process interruption exercises the actual SQLite commit boundary."""
import asyncio
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from tests.integration.test_gitea_terminal_reentry import _closeout
from tests.integration.test_gitea_terminal_transaction import _worker
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


async def _wait_file(path, task):
    async with asyncio.timeout(30):
        while not await asyncio.to_thread(path.exists):
            if task.done():
                result = await task
                pytest.fail(f'child exited {result.returncode}: {result.stderr!r}')
            await asyncio.sleep(0.02)


@pytest.mark.parametrize('boundary', ['before-commit', 'after-commit'])
# Layer: integration
async def test_native_closeout_death_preserves_all_or_none_local_terminal_records(tmp_path, boundary):
    worker, _adapter, db = _worker(tmp_path)
    supervisor = CommandProcessSupervisor(tmp_path, cancellation_event='test_gitea_closeout_process_cancelled')
    task = asyncio.create_task(supervisor.run(
        [sys.executable, '-m', 'tests.helpers.gitea_terminal_worker', str(tmp_path), boundary],
        cwd=ROOT, environment={**os.environ, 'PYTHONPATH': str(ROOT), 'ORKET_DISABLE_SANDBOX': '1'}, timeout_seconds=45))
    files = AsyncFileTools(tmp_path)
    try:
        await _wait_file(tmp_path/'work-ready.txt', task)
        before = await logical_state(db)
        await files.write_file('allow-closeout.txt', 'proceed')
        await _wait_file(tmp_path/'closeout-ready.txt', task)
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
    assert await files.read_file('remote-final-state.txt') == 'code_review'
    assert await files.read_file('work-ready.txt') == 'physical effect observed'
    run_id = worker.control_plane_execution_service.run_id_for(card_id='7', lease_epoch=1)
    truth = await worker.control_plane_execution_service.publication.repository.get_final_truth(run_id=run_id)
    if boundary == 'after-commit':
        assert truth.result_class.value == 'success'
        await _closeout(worker)
        assert await logical_state(db) == visible
    else:
        assert truth is None
