"""Real SDK request, native sink barriers and selected-error observations."""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path
from types import SimpleNamespace

from orket.adapters.observability import log_publication
from orket.adapters.storage.sdk_workload_exchange import SdkWorkloadExchange
from orket.extensions import sdk_workload_runner
from tests.helpers.lifetime_finalizer_native import AppendHold
from tests.helpers.sdk_lifetime import sdk_request

EVENT = 'sdk_workload_process_uncertain'
PRIOR = 'pre-existing SDK uncertainty note'
SOURCE = '''import json, os, time
from pathlib import Path
def run(ctx, payload):
    root = Path(ctx.workspace_root)
    (root / "sdk-effect").write_text("executed")
    (root / "ready.tmp").write_text(json.dumps({"pid": os.getpid()}))
    (root / "ready.tmp").replace(root / "ready.json")
    deadline = time.monotonic() + 20
    while not (root / "release-sdk").exists() and time.monotonic() < deadline:
        time.sleep(.01)
    os._exit(23)
'''


def request_missing_result(root):
    options = sdk_request(root)
    source = Path(options['extension'].path) / (options['workload'].entrypoint.split(':', 1)[0] + '.py')
    source.write_text(SOURCE, encoding='utf-8')
    return options


def failure_for(kind):
    if kind == 'success':
        return None
    failure = {'PermissionError': PermissionError('controlled native diagnostic refusal'),
        'CancelledError': asyncio.CancelledError('native SDK diagnostic cancellation'),
        'SystemExit': SystemExit(65), 'KeyboardInterrupt': KeyboardInterrupt('native SDK diagnostic fatal'),
        'BaseException': BaseException('native SDK diagnostic base failure')}[kind]
    failure.__cause__ = LookupError('retained SDK diagnostic cause')
    return failure


async def arrange_sinks(root, stage, failure, monkeypatch):
    append = AppendHold(EVENT, failure if stage == 'append' else None)
    append.install(monkeypatch)
    if stage == 'handler':
        append.release.set()
    handler = await asyncio.to_thread(logging.FileHandler, root / 'diagnostic.log', encoding='utf-8')
    handler.addFilter(lambda record: record.getMessage() == EVENT)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            worker=None, calls=0, expired=False, record=None)
    emit = handler.emit

    def held(record):
        state.calls += 1
        state.worker, state.record = threading.get_ident(), record.orket_record
        emit(record)  # Actual standard FileHandler flush before controlled acknowledgement.
        state.entered.set()
        try:
            if stage == 'handler':
                state.expired = not state.release.wait(10)
                assert not state.expired, 'SDK standard handler release missing'
                if failure is not None:
                    raise failure
        finally:
            state.finished.set()

    monkeypatch.setattr(handler, 'emit', held)
    logger = logging.getLogger('tests.sdk.diagnostic.' + root.name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)
    monkeypatch.setattr(log_publication, '_logger', logger)
    return append, handler, logger, state, append if stage == 'append' else state


def capture_errors(monkeypatch):
    selected, reads = [], []
    initialize = sdk_workload_runner.SdkSubprocessExecutionUncertain.__init__
    read_result = SdkWorkloadExchange.read_result

    def observed(owner, *args):
        initialize(owner, *args)
        BaseException.add_note(owner, PRIOR)
        selected.append(owner)

    def actual_read(owner):
        try:
            return read_result(owner)
        except FileNotFoundError as error:
            reads.append(error)
            raise

    monkeypatch.setattr(sdk_workload_runner.SdkSubprocessExecutionUncertain, '__init__', observed)
    monkeypatch.setattr(SdkWorkloadExchange, 'read_result', actual_read)
    return selected, reads


def assert_outcome(outcome, primary, read_error, failure, cause, stop):
    assert outcome is primary and outcome.__cause__ is read_error and outcome.__context__ is read_error
    assert outcome.__suppress_context__ is True
    if failure is not None:
        assert outcome.diagnostic_error is failure
        assert failure.__cause__ is cause
        kind = type(failure).__name__
    elif stop != 'none':
        assert type(outcome.diagnostic_error) is asyncio.CancelledError
        assert outcome.diagnostic_error.args == (('first later finalizer interruption',) if stop == 'cancel' else ())
        kind = 'CancelledError'
    else:
        assert not hasattr(outcome, 'diagnostic_error')
        kind = None
    assert outcome.__notes__ == [PRIOR] + ([f'Uncertainty diagnostic failed: {kind}'] if kind else [])
    return {'primary_identity': True, 'original_read_cause_context': True,
            'secondary_type': kind, 'native_secondary_identity': True if failure is not None else None,
            'native_secondary_cause_identity': True if failure is not None else None,
            'notes': list(outcome.__notes__)}
