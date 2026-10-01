"""Integration: real command cleanup and native supporting append/handler effects."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.application.services import outward_connector_service
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / 'helpers/outward_diagnostic_worker.py'
CASES = [('success', 'none'), ('success', 'cancel'), ('success', 'timeout'), ('OSError', 'cancel'),
         ('LookupError', 'cancel'), ('CancelledError', 'cancel'), ('SystemExit', 'cancel'), ('KeyboardInterrupt', 'cancel')]


@pytest.mark.parametrize('stage', ['append', 'fallback'])
@pytest.mark.parametrize('kind,stop', CASES)
async def test_outward_diagnostic_preserves_real_command_cancellation(tmp_path, stage, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [stage, kind, stop], record_property)
    assert (data['stage'], data['kind'], data['stop']) == (stage, kind, stop)
    assert data['caller_cancel_requests'] == {'none': 1, 'cancel': 3, 'timeout': 2}[stop]
    assert data['primary_identity'] and data['primary_graph_preserved']
    assert data['overridden_note_hook_calls'] == 0
    assert data['diagnostic_marker'] == (kind in {'LookupError', 'CancelledError', 'SystemExit', 'KeyboardInterrupt'})
    assert data['native_sinks_settled'] and data['task_settled_before_emergency']
    assert data['handler_closed_before_return'] and data['logging_binding_restored']
    assert data['append_calls'] == 1 and data['handler_calls'] == int(stage == 'fallback' or kind == 'OSError')
    assert all(row['status'] in {'absent', 'reused'} for row in data['processes_before_release'].values())
    expected = await asyncio.to_thread(lambda: {
        'path': str(Path(outward_connector_service.__file__).resolve()),
        'sha256': hashlib.sha256(Path(outward_connector_service.__file__).read_bytes()).hexdigest()})
    assert data['source_origins'][outward_connector_service.__name__] == expected
