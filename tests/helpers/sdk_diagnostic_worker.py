"""Isolated real SDK missing-result flow and native diagnostic controls."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.adapters.observability import log_publication, logging_context
from orket.core.contracts.logging_inputs import LoggingInputs
from orket.extensions import sdk_workload_runner
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.lifetime_finalizer_native import (
    arrange_finalizer_interruption,
    await_ready,
    healthy_next_command,
    public_caller,
)
from tests.helpers.log_process_receipts import process_readback
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_diagnostic_controls import (
    EVENT,
    arrange_sinks,
    assert_outcome,
    capture_errors,
    failure_for,
    request_missing_result,
)


async def observe_retained(root, primary, identity):
    lifetime = primary.lifetime
    assert lifetime.reason == 'completed' and lifetime.returncode == 23
    assert lifetime.cleanup_confirmed and lifetime.capture_complete and primary.phase == 'result-read'
    pids = [row['pid'] for row in identity['processes']]
    assert pids.index(lifetime.command_pid) < pids.index(lifetime.supervisor_pid) <= pids.index(lifetime.transport_pid)
    processes = await asyncio.to_thread(process_readback,
        {row['pid']: row['create_time'] for row in identity['processes']})
    assert processes and all(row['status'] in {'absent', 'reused'} for row in processes.values())
    exchange = primary.exchange_path
    request = await asyncio.to_thread((exchange / 'request.json').read_bytes)
    assert not await asyncio.to_thread((exchange / 'result.json').exists)
    assert await asyncio.to_thread((root / 'sdk-effect').read_text, encoding='utf-8') == 'executed'
    await asyncio.to_thread(write_payload_with_diff_ledger, root / 'process-before-release.json',
        {'live_lineage': identity, 'lifetime': lifetime.lifetime(), 'readback': processes,
         'exchange': str(exchange), 'request_sha256': hashlib.sha256(request).hexdigest()})
    return processes, request


async def observe(root, stage, kind, stop, monkeypatch, record):
    failure = failure_for(kind)
    cause = failure.__cause__ if failure is not None else None
    append, handler, logger, state, barrier = await arrange_sinks(root, stage, failure, monkeypatch)
    selected, reads = capture_errors(monkeypatch)
    options = await asyncio.to_thread(request_missing_result, root)
    active = asyncio.create_task(public_caller(sdk_workload_runner.run_sdk_workload_in_subprocess(**options)))
    waiter = active
    try:
        identity = await await_ready(root / 'ready.json', active)
        await asyncio.to_thread((root / 'release-sdk').touch)
        assert await asyncio.to_thread(barrier.entered.wait, 10), 'SDK uncertainty diagnostic was not reached'
        primary, = selected
        read_error, = reads
        processes, request = await observe_retained(root, primary, identity)
        waiter = await arrange_finalizer_interruption(active, stop)
        assert await sqlite_response(root / 'responsive.sqlite3', record) < .5
        done, _ = await asyncio.wait({waiter}, timeout=.1)
        assert not done and not active.done() and not barrier.finished.is_set()
        assert active.cancelling() == {'none': 0, 'cancel': 2, 'timeout': 1}[stop]
        assert barrier.worker != threading.get_ident() and not barrier.expired
        barrier.release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        graph = assert_outcome(outcome, primary, read_error, failure, cause, stop)
        assert state.calls == 1 and state.finished.is_set() and not state.expired
        appended = stage == 'append' or failure is None
        assert append.calls == int(appended) and (not appended or append.finished.is_set()) and not append.expired
        records = [json.loads(line) for line in
            (await asyncio.to_thread((root / 'orket.log').read_text, encoding='utf-8')).splitlines()]
        assert len([row for row in records if row['event'] == EVENT]) == int(appended)
        assert state.record['data']['phase'] == primary.phase
        assert state.record['data']['exchange_path'] == str(primary.exchange_path)
        assert state.record['data']['process_lifetime'] == primary.lifetime.lifetime()
        assert EVENT in await asyncio.to_thread((root / 'diagnostic.log').read_text, encoding='utf-8')
        assert await asyncio.to_thread((primary.exchange_path / 'request.json').read_bytes) == request
        assert not await asyncio.to_thread((primary.exchange_path / 'result.json').exists)
        healthy = await healthy_next_command(root)
        return {'stage': stage, 'kind': kind, 'stop': stop, 'caller_cancel_requests': active.cancelling(),
            'live_lineage': identity, 'processes_before_release': processes, 'lifetime': primary.lifetime.lifetime(),
            'exchange_retained': str(primary.exchange_path), 'request_retained': True, 'result_absent': True,
            'append_calls': append.calls, 'handler_calls': state.calls, 'native_sinks_settled': True,
            'task_settled_before_emergency': active.done(), 'healthy_next_lifetime': healthy, **graph}
    finally:
        append.release.set()
        state.release.set()
        if not active.done():
            active.cancel('fixture emergency cancellation')
        await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)
        logger.removeHandler(handler)
        await asyncio.to_thread(handler.close)
        assert handler.stream is None


async def exercise(root, stage, kind, stop):
    prepared = await logging_context.prepare_logging(LoggingInputs(root))
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch, logging_context.bind_logging(prepared):
        result = await observe(root, stage, kind, stop, monkeypatch,
            lambda name, value: observations.append({'name': name, 'value': value}))
    assert logging_context.selected_logging(required=False) is None
    assert log_publication._log_writer_thread.is_alive() and log_publication._log_write_queue.qsize() == 0
    return {**result, 'observations': observations, 'logging_binding_restored': True,
            'handler_closed_before_return': True, 'writer_shutdown': 'process-exit; no in-process stop or join'}


def main():
    root, stage, kind, stop = Path(sys.argv[1]).resolve(), *sys.argv[2:]
    result = asyncio.run(exercise(root, stage, kind, stop))
    process = psutil.Process()
    modules = (owned_io, sdk_workload_runner, log_publication)
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={'pid': process.pid, 'create_time': process.create_time()},
        source_origins={module.__name__: {'path': str(Path(module.__file__).resolve()),
            'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for module in modules})
    write_payload_with_diff_ledger(root / 'result.json', result)


if __name__ == '__main__':
    main()
