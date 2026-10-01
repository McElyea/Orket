"""Native sink controls for public connector interruption observations."""
from __future__ import annotations

import asyncio
import logging
import threading

from orket.application.services import outward_connector_service
from tests.helpers.lifetime_finalizer_native import AppendHold
from tests.helpers.lifetime_finalizer_worker import capture_cancellation

EVENT = 'outward_connector_interrupted'
NOTE = 'E_OWNED_DIAGNOSTIC_FAILED'
PRIOR = 'pre-existing connector note'
EXPECTED = 'Interrupted connector telemetry for run_command failed (OSError); diagnostic sink failed (OSError).'


def failure_for(kind):
    if kind == 'success':
        return None
    failure = {'OSError': OSError('controlled append or handler refusal'),
        'LookupError': LookupError('unexpected native diagnostic failure'),
        'CancelledError': asyncio.CancelledError('native diagnostic cancellation'),
        'SystemExit': SystemExit(63), 'KeyboardInterrupt': KeyboardInterrupt('native diagnostic fatal')}[kind]
    failure.__cause__ = ValueError('retained diagnostic cause')
    return failure


class HeldDiagnosticHandler(logging.FileHandler):
    def __init__(self, path, *, failure, held):
        super().__init__(path, encoding='utf-8')
        self.failure, self.held = failure, held
        self.entered, self.unblock, self.finished = threading.Event(), threading.Event(), threading.Event()
        self.calls, self.worker, self.expired = 0, None, False
        self.errors = []

    def emit(self, record):
        self.calls += 1
        self.worker = threading.get_ident()
        self.errors.append(record.exc_info[1] if record.exc_info else None)
        super().emit(record)  # Actual standard file sink and flush precede acknowledgement.
        self.entered.set()
        try:
            if self.held:
                self.expired = not self.unblock.wait(10)
                assert not self.expired, 'diagnostic handler release missing'
            if self.failure is not None:
                raise self.failure
        finally:
            self.finished.set()


async def arrange_sinks(root, stage, kind, monkeypatch):
    append = AppendHold(EVENT, failure_for(kind) if stage == 'append' else failure_for('OSError'))
    append.install(monkeypatch)
    handler = await asyncio.to_thread(HeldDiagnosticHandler, root / 'diagnostic.log',
        failure=failure_for(kind) if stage == 'fallback' else None, held=stage == 'fallback')
    logger = logging.getLogger('tests.outward.diagnostic.' + root.name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    monkeypatch.setattr(outward_connector_service, 'logger', logger)
    if stage == 'fallback':
        append.release.set()
    return append, handler, logger, append if stage == 'append' else handler


def capture_primary(monkeypatch):
    selected = capture_cancellation(monkeypatch)
    hooks = []

    def adverse_note(_owner, note):
        hooks.append(note)
        raise AssertionError('diagnostics must not call an overridden primary note hook')

    monkeypatch.setattr(outward_connector_service.CommandProcessCancelled, 'add_note', adverse_note)
    return selected, hooks


def assert_primary(outcome, primary, graph, hooks, stage, kind):
    assert outcome is primary
    assert (primary.__cause__, primary.__context__, primary.__suppress_context__) == graph
    assert not hooks
    unexpected = kind in ('LookupError', 'CancelledError', 'SystemExit', 'KeyboardInterrupt')
    expected = [PRIOR, NOTE] if unexpected else [PRIOR, EXPECTED] if stage == 'fallback' and kind == 'OSError' else [PRIOR]
    assert primary.__notes__ == expected
    return {'primary_identity': True, 'primary_graph_preserved': True, 'notes': list(primary.__notes__),
            'overridden_note_hook_calls': len(hooks), 'diagnostic_marker': unexpected}
