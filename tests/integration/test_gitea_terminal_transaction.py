"""Real SQLite and filesystem controls for Gitea worker closeout authority."""
import asyncio

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    build_gitea_state_control_plane_checkpoint_service,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    build_gitea_state_control_plane_execution_service,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    build_gitea_state_control_plane_lease_service,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    build_gitea_state_control_plane_reservation_service,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from tests.helpers.gitea_control_plane_clock import ordered_utc_clock
from tests.integration.test_gitea_state_worker_control_plane import _FakeAdapter, _lease_response
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WRITES = ('save_step_record', 'append_effect_journal_entry', 'save_final_truth',
          'save_attempt_record', 'save_run_record', 'append_lease_record', 'save_resource_record')


def _worker(tmp_path):
    now = ordered_utc_clock()
    db = tmp_path/'control_plane.sqlite3'
    adapter = _FakeAdapter()
    adapter.acquire_result = _lease_response(card_id='7',worker_id='worker-a',epoch=1,version=4,
                                            expires_at='2026-03-24T01:01:00+00:00')
    worker = GiteaStateWorker(adapter=adapter,worker_id='worker-a',renew_interval_seconds=30,
        control_plane_execution_service=build_gitea_state_control_plane_execution_service(db, now_utc=now),
        control_plane_lease_service=build_gitea_state_control_plane_lease_service(db, now_utc=now),
        control_plane_checkpoint_service=build_gitea_state_control_plane_checkpoint_service(db),
        control_plane_reservation_service=build_gitea_state_control_plane_reservation_service(db))
    return worker, adapter, db


@pytest.mark.parametrize(('method', 'work_fails'),
                         [(method, failed) for failed in (False, True)
                          for method in (*WRITES, 'save_recovery_decision')
                          if failed or method != 'save_recovery_decision'])
@pytest.mark.parametrize('cancel',[False,True],ids=['error','cancel'])
# Layer: integration
async def test_gitea_closeout_interruption_restores_local_authority(tmp_path,monkeypatch,method,cancel,work_fails):
    worker,adapter,db = _worker(tmp_path)
    before, hits = None, 0
    owner = AsyncControlPlaneExecutionRepository if method in {'save_step_record','save_run_record','save_attempt_record'} else AsyncControlPlaneRecordRepository
    original = getattr(owner,method)

    async def interrupted(repository,**kwargs):
        nonlocal hits
        result = await original(repository,**kwargs)
        if before is not None:
            hits += 1
            if cancel:
                raise asyncio.CancelledError('closeout write interrupted')
            raise RuntimeError('closeout write interrupted')
        return result

    async def work(_card):
        nonlocal before
        await AsyncFileTools(tmp_path).write_file('observed-work.txt','executed')
        before = await logical_state(db)
        if work_fails:
            raise RuntimeError('work failed after physical effect')
        return {'ok':True}

    monkeypatch.setattr(owner,method,interrupted)
    with pytest.raises(asyncio.CancelledError if cancel else (RuntimeError,ValueError)):
        await worker.run_once(work_fn=work)
    assert hits >= 1
    assert await logical_state(db)==before
    assert await AsyncFileTools(tmp_path).read_file('observed-work.txt')=='executed'
    assert len([call for call in adapter.calls if call[0]=='release_or_fail'])==1


# Layer: integration
async def test_gitea_reversed_release_clock_cannot_retain_terminal_success(tmp_path,monkeypatch):
    worker,adapter,db = _worker(tmp_path)
    before = None

    async def work(_card):
        nonlocal before
        await AsyncFileTools(tmp_path).write_file('observed-work.txt','executed')
        before = await logical_state(db)
        monkeypatch.setattr(worker.control_plane_lease_service,'now_utc',
                            lambda:'2026-03-24T01:00:00+00:00')
        return {'ok':True}

    with pytest.raises(ValueError,match='timestamps must increase'):
        await worker.run_once(work_fn=work)
    assert await logical_state(db)==before
    assert len([call for call in adapter.calls if call[0]=='release_or_fail'])==1


# Layer: integration
async def test_gitea_uncertain_remote_closeout_is_not_dispatched_twice(tmp_path,monkeypatch):
    worker,adapter,db = _worker(tmp_path)
    original = adapter.release_or_fail
    before = None

    async def failed_after_effect(*args,**kwargs):
        await original(*args,**kwargs)
        await AsyncFileTools(tmp_path).write_file('remote-observed.txt',kwargs['final_state'])
        raise OSError('response lost after remote mutation')

    async def work(_card):
        nonlocal before
        before = await logical_state(db)
        return {'ok':True}

    monkeypatch.setattr(adapter,'release_or_fail',failed_after_effect)
    with pytest.raises(OSError,match='response lost'):
        await worker.run_once(work_fn=work)
    assert len([call for call in adapter.calls if call[0]=='release_or_fail'])==1
    assert await logical_state(db)==before
    assert await AsyncFileTools(tmp_path).read_file('remote-observed.txt')=='code_review'


# Layer: integration
async def test_gitea_renewal_settles_before_remote_closeout(tmp_path,monkeypatch):
    worker,adapter,_db = _worker(tmp_path)
    worker.renew_interval_seconds = 0.01
    entered, allow, renewed, work_finished = (asyncio.Event() for _ in range(4))
    original = adapter.release_or_fail

    async def renew(*_args,**_kwargs):
        entered.set()
        await allow.wait()
        renewed.set()
        return {'ok':True}

    async def release(*args,**kwargs):
        assert renewed.is_set(), 'remote closeout raced an unfinished renewal'
        return await original(*args,**kwargs)

    async def work(_card):
        await asyncio.wait_for(entered.wait(),5)
        work_finished.set()
        return {'ok':True}

    monkeypatch.setattr(adapter,'renew_lease',renew)
    monkeypatch.setattr(adapter,'release_or_fail',release)
    task = asyncio.create_task(worker.run_once(work_fn=work))
    try:
        await asyncio.wait_for(work_finished.wait(),5)
    finally:
        allow.set()
    assert await asyncio.wait_for(task,5) is True


# Layer: integration
async def test_gitea_healthy_closeout_retains_terminal_truth_and_released_lease(tmp_path,monkeypatch):
    worker,adapter,_db = _worker(tmp_path)

    async def work(_card):
        await AsyncFileTools(tmp_path).write_file('observed-work.txt','executed')
        return {'ok':True}

    assert await worker.run_once(work_fn=work) is True
    execution = worker.control_plane_execution_service
    run_id = execution.run_id_for(card_id='7',lease_epoch=1)
    run = await execution.execution_repository.get_run_record(run_id=run_id)
    attempt = await execution.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
    truth = await execution.publication.repository.get_final_truth(run_id=run_id)
    lease = await execution.publication.repository.get_latest_lease_record(lease_id='gitea-card-lease:7')
    assert run.lifecycle_state.value=='completed' and attempt.attempt_state.value=='attempt_completed'
    assert truth.result_class.value=='success' and lease.status.value=='lease_released'
    assert await AsyncFileTools(tmp_path).read_file('observed-work.txt')=='executed'
    assert len([call for call in adapter.calls if call[0]=='release_or_fail'])==1
