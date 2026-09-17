"""Local terminal reuse and owned renewal through repeated cancellation."""
import asyncio

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.gitea_state_worker import LeaseExpiredError
from tests.integration.test_gitea_terminal_transaction import _worker
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_empty_lease_expiry_error_retains_blocked_classification_and_resource_closeout(tmp_path):
    worker, adapter, _db = _worker(tmp_path)

    async def work(_):
        raise LeaseExpiredError()

    assert await worker.run_once(work_fn=work)
    run, attempt, _step, _effect, truth = await _closeout(worker, final_state='blocked', error='E_LEASE_EXPIRED')
    lease = await worker.control_plane_execution_service.publication.repository.get_latest_lease_record(
        lease_id='gitea-card-lease:7')
    assert truth.result_class.value == 'blocked' and run.lifecycle_state.value == 'failed_terminal'
    assert attempt.failure_class == 'lease_expired' and lease.status.value == 'lease_released'
    assert [call for call in adapter.calls if call[0] == 'release_or_fail'] == [
        ('release_or_fail', '7', 'blocked', 'E_LEASE_EXPIRED')]


async def _closeout(worker, *, final_state='code_review', error=None, attempt_id=None):
    execution = worker.control_plane_execution_service
    run_id = execution.run_id_for(card_id='7', lease_epoch=1)
    return await execution.publish_release_transition_and_finalize(
        run_id=run_id, attempt_id=attempt_id or execution.attempt_id_for(run_id=run_id), card_id='7',
        final_state=final_state, error=error, success_state='code_review', worker_id='worker-a',
        lease_observation=worker.adapter.acquire_result, lease_expired=False,
        lease_service=worker.control_plane_lease_service,
    )


@pytest.mark.parametrize('failed', [False, True])
# Layer: integration
async def test_terminal_reuse_preserves_complete_state_and_refuses_changed_result(tmp_path, failed):
    worker, adapter, db = _worker(tmp_path)

    async def work(_):
        await AsyncFileTools(tmp_path).write_file('effect.txt', 'observed')
        if failed:
            raise RuntimeError('work failed')
        return {'ok': True}

    await worker.run_once(work_fn=work)
    before = await logical_state(db)
    state, error = ('blocked', 'work failed') if failed else ('code_review', None)
    run, attempt, step, effect, truth = await _closeout(worker, final_state=state, error=error)
    assert run.final_truth_record_id == truth.final_truth_record_id
    assert run.current_attempt_id == attempt.attempt_id == step.attempt_id == effect.attempt_id
    assert await logical_state(db) == before
    with pytest.raises(ValueError, match='TERMINAL_IDENTITY'):
        await _closeout(worker, final_state='code_review' if failed else 'blocked', error=None if failed else 'changed')
    assert await logical_state(db) == before
    assert len([call for call in adapter.calls if call[0] == 'release_or_fail']) == 1


@pytest.mark.parametrize('corruption', ['truth_join', 'resource_namespace', 'lease_holder'])
# Layer: integration
async def test_terminal_reuse_refuses_corrupted_authority_without_repair(tmp_path, corruption):
    worker, _adapter, db = _worker(tmp_path)

    async def work(_):
        return {'ok': True}

    await worker.run_once(work_fn=work)
    service = worker.control_plane_execution_service
    run_id = service.run_id_for(card_id='7', lease_epoch=1)
    if corruption == 'truth_join':
        run = await service.execution_repository.get_run_record(run_id=run_id)
        await service.execution_repository.save_run_record(record=run.model_copy(update={'final_truth_record_id': 'other'}))
    elif corruption == 'resource_namespace':
        resource = await service.publication.repository.get_latest_resource_record(resource_id='gitea-card:7')
        await service.publication.repository.save_resource_record(record=resource.model_copy(update={
            'namespace_scope': 'issue:foreign', 'last_observed_timestamp': '2026-03-24T01:02:00+00:00'}))
    else:
        lease = await service.publication.repository.get_latest_lease_record(lease_id='gitea-card-lease:7')
        await service.publication.repository.append_lease_record(record=lease.model_copy(update={
            'holder_ref': 'gitea-worker:foreign', 'publication_timestamp': '2026-03-24T01:02:00+00:00'}))
    before = await logical_state(db)
    with pytest.raises(ValueError, match='IDENTITY|AUTHORITY_CONFLICT'):
        await _closeout(worker)
    assert await logical_state(db) == before


# Layer: integration
async def test_repeated_cancellation_waits_for_inflight_renewal_without_remote_closeout(tmp_path, monkeypatch):
    worker, adapter, db = _worker(tmp_path)
    worker.renew_interval_seconds = 0.01
    entered, allow, settled = (asyncio.Event() for _ in range(3))

    async def renew(*_args, **_kwargs):
        entered.set()
        await allow.wait()
        await AsyncFileTools(tmp_path).write_file('renewal.txt', 'settled')
        settled.set()
        return {'ok': True}

    async def work(_):
        await asyncio.Event().wait()

    monkeypatch.setattr(adapter, 'renew_lease', renew)
    task = asyncio.create_task(worker.run_once(work_fn=work))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        before = await logical_state(db)
        for _ in range(3):
            task.cancel()
            await asyncio.sleep(0.01)
            assert not task.done()
    finally:
        allow.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 5)
    assert settled.is_set()
    assert await AsyncFileTools(tmp_path).read_file('renewal.txt') == 'settled'
    assert not any(call[0] == 'release_or_fail' for call in adapter.calls)
    assert await logical_state(db) == before
