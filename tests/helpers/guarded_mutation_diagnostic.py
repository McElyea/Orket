"""Actual standard file-handler drain under a failed card mutation's retained owner."""
from __future__ import annotations

import asyncio
import logging
import threading

import pytest

from orket.adapters.execution import owned_io
from orket.application.services import card_workspace_mutation_service
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.guarded_mutation_controls import invocation, prepare_guard
from tests.helpers.outward_diagnostic_controls import HeldDiagnosticHandler
from tests.helpers.runtime_verification_hold import sqlite_response
from tests.helpers.sdk_observation_controls import public_caller
from tests.helpers.tool_runtime_controls import entered


async def observe_diagnostic(root, kind):
    repo, _completion, _accepted, hold, failure, _value = await prepare_guard(root, 'OSError')
    secondary = SystemExit(71) if kind == 'fatal' else None
    handler = await asyncio.to_thread(HeldDiagnosticHandler, root / 'guard-diagnostic.log',
        failure=secondary, held=kind == 'held')
    logger = logging.getLogger(card_workspace_mutation_service.__name__)
    old_level, old_propagate = logger.level, logger.propagate
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    operation, _args, _context = invocation(repo, hold, 'mutation', 'cancel', root)
    graph = (failure.__cause__, failure.__context__, failure.__suppress_context__)
    active = None
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(owned_io, 'logger', logger)
            active = asyncio.create_task(public_caller(operation))
            await entered(hold)
            active.cancel('initial guarded cancellation')
            await asyncio.sleep(0)
            hold.release.set()
            assert await asyncio.to_thread(handler.entered.wait, 5), 'mutation drain diagnostic was not attempted'
            elapsed = await sqlite_response(root / 'diagnostic-responsive.sqlite3', lambda *_args: None)
            before = {'route': 'diagnostic', 'kind': kind, 'stop': 'cancel', 'handler_calls': handler.calls,
                'handler_native': handler.worker != threading.get_ident(), 'watchdog_expired': handler.expired,
                'invocation_pending': not active.done(), 'sqlite_seconds': elapsed}
            await asyncio.to_thread(write_payload_with_diff_ledger, root / 'diagnostic-before-release.json', before)
            if kind == 'held':
                assert not active.done() and not handler.finished.is_set()
                active.cancel('later diagnostic cancellation')
                await asyncio.sleep(0)
                active.cancel('repeated diagnostic cancellation')
                assert not active.done()
            handler.unblock.set()
            outcome = await asyncio.wait_for(active, 10)
            assert outcome is failure
            assert (failure.__cause__, failure.__context__, failure.__suppress_context__) == graph
            assert handler.errors == [failure] and handler.calls == 1
            assert before['handler_native'] and not handler.expired and handler.finished.is_set() and elapsed < .5
            assert getattr(failure, '__notes__', []) == (['E_OWNED_DIAGNOSTIC_FAILED'] if secondary else [])
            assert 'Owned I/O failed while draining cancellation (card-workspace-mutation)' in await asyncio.to_thread(
                (root / 'guard-diagnostic.log').read_text, encoding='utf-8')
            return {**before, 'native_primary_preserved': True, 'diagnostic_settled': True,
                'diagnostic_failed_marker': secondary is not None, 'task_settled_before_emergency': active.done()}
    finally:
        hold.release.set()
        handler.unblock.set()
        try:
            if active is not None:
                await asyncio.wait_for(asyncio.gather(active, return_exceptions=True), 10)
            if hold.entered.is_set():
                assert await asyncio.to_thread(hold.finished.wait, 3)
        finally:
            logger.removeHandler(handler)
            await asyncio.to_thread(handler.close)
            logger.setLevel(old_level)
            logger.propagate = old_propagate
