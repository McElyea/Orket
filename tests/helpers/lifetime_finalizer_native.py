"""Fresh-process controls for real command/fixture cleanup and retained append."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading

import psutil

from orket.adapters.observability import log_publication
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.fixture_verification_service import FixtureVerificationService
from tests.helpers.fixture_input_controls import prepare_native, selected_time
from tests.helpers.log_process_receipts import process_readback

READY_CODE = "from pathlib import Path; import json,os,time; Path('ready.tmp').write_text(json.dumps({'pid':os.getpid()})); Path('ready.tmp').replace('ready.json'); time.sleep(30)"
FIXTURE_CODE = "def verify(data):\n    " + READY_CODE.replace('; ', '\n    ') + "\n"


class AppendHold:
    def __init__(self, event, failure):
        self.event, self.failure = event, failure
        self.entered, self.release, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.worker, self.expired = 0, None, False
        self.record = None

    def install(self, monkeypatch):
        append = log_publication._append_line_sync

        def held(path, line):
            record = json.loads(line)
            if record.get('event') != self.event:
                return append(path, line)
            self.calls += 1
            self.worker = threading.get_ident()
            append(path, line)  # Required physical append precedes the controlled acknowledgement.
            self.record = record
            self.entered.set()
            try:
                self.expired = not self.release.wait(10)
                assert not self.expired, 'lifetime finalizer release missing'
                if self.failure is not None:
                    raise self.failure
            finally:
                self.finished.set()

        monkeypatch.setattr(log_publication, '_append_line_sync', held)


async def start_public_flow(root, route):
    verification = None
    if route == 'fixture':
        verification = await asyncio.to_thread(prepare_native, root, FIXTURE_CODE)
        service = FixtureVerificationService(root, utc_now=selected_time,
            environment=dict(os.environ, ORKET_VERIFY_EXECUTION_MODE='subprocess',
                ORKET_VERIFY_ALLOW_UNSAFE_SUBPROCESS='1', ORKET_VERIFY_TIMEOUT_SEC='20',
                ORKET_RUNTIME_PROFILE='development', ORKET_PROFILE='development'))
        operation = service.verify(verification)
        ready = root / 'verification/ready.json'
    else:
        supervisor = CommandProcessSupervisor(root, cancellation_event='finalizer_command_cancelled')
        operation = supervisor.run([sys.executable, '-I', '-c', READY_CODE], cwd=root,
            environment=dict(os.environ), timeout_seconds=20)
        ready = root / 'ready.json'
    return operation, ready, verification


async def public_caller(operation):
    try:
        await operation
    except BaseException as failure:
        # Catch at the actual public caller only. A fatal escape from an internal
        # Task still aborts this isolated interpreter and fails the parent control.
        return failure
    raise AssertionError('the native command was expected to be interrupted')


def capture_live_lineage(pid):
    anchor = psutil.Process()
    process = psutil.Process(pid)
    rows, observed = [], []
    while process.pid != anchor.pid:
        assert process.pid not in {row['pid'] for row in rows}, 'process ancestry cycle'
        parent = process.parent()
        assert parent is not None, 'command ancestry did not reach the isolated caller'
        rows.append({'pid': process.pid, 'create_time': process.create_time(), 'parent_pid': parent.pid})
        observed.append(process)
        process = parent
    assert rows and process.create_time() == anchor.create_time()
    for process, row in zip(observed, rows, strict=True):
        assert process.is_running() and process.status() != psutil.STATUS_ZOMBIE
        assert process.create_time() == row['create_time'] and process.ppid() == row['parent_pid']
    return {'ready_pid': pid, 'processes': rows,
            'caller': {'pid': anchor.pid, 'create_time': anchor.create_time()}}


async def await_ready(path, task):
    async with asyncio.timeout(10):
        while not await asyncio.to_thread(path.exists):
            assert not task.done(), 'public flow escaped before child readiness'
            await asyncio.sleep(.025)
        record = json.loads(await asyncio.to_thread(path.read_text, encoding='utf-8'))
        return await asyncio.to_thread(capture_live_lineage, record['pid'])


async def assert_command_reaped(hold, identity):
    lifetime = hold.record['data']
    assert lifetime['cleanup_confirmed'] is True and lifetime['reason'] == 'cancelled'
    lineage = identity['processes']
    pids = [row['pid'] for row in lineage]
    assert identity['ready_pid'] == pids[0]
    assert all(lifetime[name] in pids for name in ('command_pid', 'supervisor_pid', 'transport_pid'))
    assert pids.index(lifetime['command_pid']) < pids.index(lifetime['supervisor_pid'])
    assert pids.index(lifetime['supervisor_pid']) <= pids.index(lifetime['transport_pid'])
    assert lineage[-1]['parent_pid'] == identity['caller']['pid']
    identities = {row['pid']: row['create_time'] for row in lineage}
    observed = await asyncio.to_thread(process_readback, identities)
    assert observed and all(row['status'] in {'absent', 'reused'} for row in observed.values())
    return observed


async def arrange_finalizer_interruption(active, stop):
    if stop == 'cancel':
        active.cancel('first later finalizer interruption')
        await asyncio.sleep(0)
        active.cancel('second later finalizer interruption')
    if stop == 'timeout':
        return asyncio.create_task(asyncio.wait_for(active, .02))
    return active


async def healthy_next_command(root):
    result = await CommandProcessSupervisor(root, cancellation_event='healthy_not_cancelled').run(
        [sys.executable, '-I', '-c', "print('healthy-next')"], cwd=root,
        environment=dict(os.environ), timeout_seconds=10)
    assert result.cleanup_confirmed and result.capture_complete and result.returncode == 0
    assert result.stdout.strip() == b'healthy-next'
    observed = await asyncio.to_thread(process_readback,
        {pid: None for pid in (result.transport_pid, result.supervisor_pid, result.command_pid) if pid is not None})
    assert all(row['status'] in {'absent', 'reused'} for row in observed.values())
    return result.lifetime()
