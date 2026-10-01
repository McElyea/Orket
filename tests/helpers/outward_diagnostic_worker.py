"""Isolated real command and supporting-sink failure observation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

import orket
from orket.adapters.execution import owned_io
from orket.adapters.observability import log_publication, logging_context
from orket.application.services import outward_connector_service
from orket.core.contracts.logging_inputs import LoggingInputs
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.lifetime_finalizer_native import (
    READY_CODE,
    arrange_finalizer_interruption,
    assert_command_reaped,
    await_ready,
    healthy_next_command,
    public_caller,
)
from tests.helpers.outward_diagnostic_controls import EVENT, PRIOR, arrange_sinks, assert_primary, capture_primary
from tests.helpers.runtime_verification_hold import sqlite_response


async def observe(root, stage, kind, stop, monkeypatch, record):
    append, handler, logger, barrier = await arrange_sinks(root, stage, kind, monkeypatch)
    release = append.release if stage == 'append' else handler.unblock
    selected, hooks = capture_primary(monkeypatch)
    service = await outward_connector_service.OutwardConnectorService.for_workspace(root)
    command = [sys.executable, '-I', '-c', READY_CODE]
    active = asyncio.create_task(public_caller(service.invoke_with_result('run_command', {'command': command})))
    waiter = active
    try:
        identity = await await_ready(root / 'ready.json', active)
        active.cancel('initial public connector cancellation')
        assert await asyncio.to_thread(barrier.entered.wait, 10), 'supporting sink was not reached'
        primary, = selected
        BaseException.add_note(primary, PRIOR)
        graph = primary.__cause__, primary.__context__, primary.__suppress_context__
        lifetime = append.record['data']['process_lifetime']
        assert lifetime == primary.lifetime.lifetime()
        processes = await assert_command_reaped(SimpleNamespace(record={'data': lifetime}), identity)
        await asyncio.to_thread(write_payload_with_diff_ledger, root / 'process-before-release.json',
            {'live_lineage': identity, 'lifetime': lifetime, 'readback': processes})
        waiter = await arrange_finalizer_interruption(active, stop)
        assert await sqlite_response(root / 'responsive.sqlite3', record) < .5
        done, _ = await asyncio.wait({waiter}, timeout=.1)
        assert not done and not active.done() and not barrier.finished.is_set()
        assert active.cancelling() == {'none': 1, 'cancel': 3, 'timeout': 2}[stop]
        assert barrier.worker != threading.get_ident() and not barrier.expired
        release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        graph_result = assert_primary(outcome, primary, graph, hooks, stage, kind)
        assert append.calls == 1 and append.finished.is_set() and not append.expired
        assert handler.calls == int(stage == 'fallback' or kind == 'OSError')
        assert not handler.expired and (not handler.calls or handler.finished.is_set())
        if handler.calls:
            assert handler.worker != threading.get_ident() and handler.errors == [append.failure]
        records = [json.loads(line) for line in
            (await asyncio.to_thread((root / 'orket.log').read_text, encoding='utf-8')).splitlines()]
        assert [row for row in records if row['event'] == EVENT] == [append.record]
        assert append.record['data']['observation'] == 'cancelled' and 'outcome' not in append.record['data']
        assert 'Unable to record interrupted connector timing for run_command' in (
            await asyncio.to_thread((root / 'diagnostic.log').read_text, encoding='utf-8')) if handler.calls else True
        assert log_publication._log_write_queue.qsize() == 0
        healthy = await healthy_next_command(root)
        return {'stage': stage, 'kind': kind, 'stop': stop, 'caller_cancel_requests': active.cancelling(),
            'live_lineage': identity, 'processes_before_release': processes, 'physical_record': append.record,
            'append_calls': append.calls, 'handler_calls': handler.calls, 'native_sinks_settled': True,
            'task_settled_before_emergency': active.done(), 'healthy_next_lifetime': healthy, **graph_result}
    finally:
        append.release.set()
        handler.unblock.set()
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
    assert log_publication._log_writer_thread.is_alive()
    return {**result, 'observations': observations, 'logging_binding_restored': True,
            'handler_closed_before_return': True, 'writer_shutdown': 'process-exit; no in-process stop or join'}


def main():
    root, stage, kind, stop = Path(sys.argv[1]).resolve(), *sys.argv[2:]
    result = asyncio.run(exercise(root, stage, kind, stop))
    process = psutil.Process()
    modules = (owned_io, outward_connector_service, log_publication)
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={'pid': process.pid, 'create_time': process.create_time()},
        source_origins={module.__name__: {'path': str(Path(module.__file__).resolve()),
            'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for module in modules})
    write_payload_with_diff_ledger(root / 'result.json', result)


if __name__ == '__main__':
    main()
