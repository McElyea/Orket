"""Isolated public-flow probe; fatal internal task escape must fail this child."""
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
from orket.application.services import command_process_supervisor, fixture_verification_service
from orket.core.contracts.logging_inputs import LoggingInputs
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.lifetime_finalizer_native import (
    AppendHold,
    arrange_finalizer_interruption,
    assert_command_reaped,
    await_ready,
    healthy_next_command,
    public_caller,
    start_public_flow,
)
from tests.helpers.runtime_verification_hold import sqlite_response


def selected_failure(kind):
    if kind == 'success':
        return None
    failure = {'OSError': OSError('native append acknowledgement failed'),
        'TypeError': TypeError('native append type failure'),
        'CancelledError': asyncio.CancelledError('native append cancellation'),
        'SystemExit': SystemExit(61), 'KeyboardInterrupt': KeyboardInterrupt('native append fatal')}[kind]
    failure.__cause__ = LookupError('retained native cause')
    return failure


def capture_cancellation(monkeypatch):
    selected = []
    initialize = command_process_supervisor.CommandProcessCancelled.__init__

    def observed(owner, lifetime):
        initialize(owner, lifetime)
        selected.append(owner)

    monkeypatch.setattr(command_process_supervisor.CommandProcessCancelled, '__init__', observed)
    return selected


def assert_outcome(route, hold, outcome, selected, cause):
    expected_domain_cancel = route == 'fixture' or hold.failure is None or isinstance(hold.failure, OSError)
    assert len(selected) == int(expected_domain_cancel)
    original_cancel = selected[0] if selected else None
    if original_cancel is not None:
        assert original_cancel.lifetime.cleanup_confirmed
    if hold.failure is None:
        assert outcome is original_cancel and outcome.__cause__ is None
    elif route == 'command' and isinstance(hold.failure, OSError):
        assert outcome is original_cancel and outcome.__cause__ is hold.failure
        assert hold.failure.__cause__ is cause
    else:
        assert outcome is hold.failure and outcome.__cause__ is cause
        if route == 'fixture':
            assert outcome.__context__ is original_cancel
    return {'outcome_type': type(outcome).__name__, 'selected_cancel_identity': outcome is original_cancel,
            'domain_cancel_created': original_cancel is not None,
            'native_failure_identity': outcome is hold.failure,
            'native_cause_identity': None if hold.failure is None else hold.failure.__cause__ is cause,
            'fixture_primary_context_identity': outcome.__context__ is original_cancel
                if route == 'fixture' and hold.failure is not None else None,
            'command_failure_cause_identity': outcome.__cause__ is hold.failure
                if route == 'command' and isinstance(hold.failure, OSError) else None}


async def observe(root, route, kind, stop, monkeypatch, record):
    event = 'fixture_verification_cancelled' if route == 'fixture' else 'finalizer_command_cancelled'
    hold = AppendHold(event, selected_failure(kind))
    cause = None if hold.failure is None else hold.failure.__cause__
    hold.install(monkeypatch)
    selected = capture_cancellation(monkeypatch)
    operation, ready, verification = await start_public_flow(root, route)
    active = asyncio.create_task(public_caller(operation))
    waiter = active
    try:
        identity = await await_ready(ready, active)
        active.cancel('initial public command cancellation')
        assert await asyncio.to_thread(hold.entered.wait, 10), 'finalizer native append was not reached'
        processes = await assert_command_reaped(hold, identity)
        await asyncio.to_thread(write_payload_with_diff_ledger, root / 'process-before-release.json',
            {'live_lineage': identity, 'lifetime': hold.record['data'], 'readback': processes})
        waiter = await arrange_finalizer_interruption(active, stop)
        assert await sqlite_response(root / 'responsive.sqlite3', record) < .5
        done, _ = await asyncio.wait({waiter}, timeout=.1)
        assert not done and not active.done() and not hold.finished.is_set()
        assert active.cancelling() == {'none': 1, 'cancel': 3, 'timeout': 2}[stop]
        assert hold.worker != threading.get_ident() and not hold.expired
        hold.release.set()
        outcome = await asyncio.wait_for(waiter, 10)
        graph = assert_outcome(route, hold, outcome, selected, cause)
        assert hold.calls == 1 and hold.finished.is_set() and not hold.expired
        records = [json.loads(line) for line in
            (await asyncio.to_thread((root / 'orket.log').read_text, encoding='utf-8')).splitlines()]
        retained = [row for row in records if row['event'] == event]
        assert retained == [hold.record] and retained[0]['data']['cleanup_confirmed'] is True
        if selected:
            assert selected[0].lifetime.lifetime() == {key: value for key, value in retained[0]['data'].items() if key != 'runtime_event'}
        if verification is not None:
            assert verification.scenarios[0].status == 'pending' and verification.last_run is None
        assert log_publication._log_write_queue.qsize() == 0
        healthy = await healthy_next_command(root)
        return {'route': route, 'kind': kind, 'stop': stop, 'caller_cancel_requests': active.cancelling(),
            'native_calls': hold.calls, 'native_thread': True, 'native_settled': True, 'watchdog_expired': hold.expired,
            'live_lineage': identity, 'physical_record': retained[0], 'processes_before_release': processes, 'healthy_next_lifetime': healthy,
            'task_settled_before_emergency': active.done(),
            'verification_result_unpublished': None if verification is None else True, **graph}
    finally:
        hold.release.set()
        if not active.done():
            active.cancel('fixture emergency cancellation')
        await asyncio.wait_for(asyncio.gather(active, waiter, return_exceptions=True), 10)


async def exercise(root, route, kind, stop):
    prepared = await logging_context.prepare_logging(LoggingInputs(root))
    observations = []
    with pytest.MonkeyPatch.context() as monkeypatch, logging_context.bind_logging(prepared):
        result = await observe(root, route, kind, stop, monkeypatch,
            lambda name, value: observations.append({'name': name, 'value': value}))
    assert logging_context.selected_logging(required=False) is None
    assert log_publication._log_writer_thread.is_alive()
    return {**result, 'observations': observations, 'logging_binding_restored': True,
            'writer_shutdown': 'process-exit; no in-process stop or join is claimed'}


def main():
    root, route, kind, stop = Path(sys.argv[1]).resolve(), *sys.argv[2:]
    result = asyncio.run(exercise(root, route, kind, stop))
    process = psutil.Process()
    source_modules = (owned_io, command_process_supervisor, fixture_verification_service, log_publication)
    result.update(interpreter=sys.executable, prefix=sys.prefix, origin=str(Path(orket.__file__).resolve()),
        owner_origin=str(Path(owned_io.__file__).resolve()),
        owner_sha256=hashlib.sha256(Path(owned_io.__file__).read_bytes()).hexdigest(),
        process_identity={'pid': process.pid, 'create_time': process.create_time()},
        source_origins={module.__name__: {'path': str(Path(module.__file__).resolve()),
            'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()} for module in source_modules})
    write_payload_with_diff_ledger(root / 'result.json', result)


if __name__ == '__main__':
    main()
