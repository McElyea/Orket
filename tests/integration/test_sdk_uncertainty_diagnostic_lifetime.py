"""Integration: actual SDK effect/result absence and retained secondary diagnostics."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.extensions import sdk_workload_runner
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / 'helpers/sdk_diagnostic_worker.py'
CASES = [('success', 'none'), ('success', 'cancel'), ('success', 'timeout'), ('PermissionError', 'cancel'),
         ('CancelledError', 'cancel'), ('SystemExit', 'cancel'), ('KeyboardInterrupt', 'cancel'), ('BaseException', 'cancel')]


@pytest.mark.parametrize('stage', ['append', 'handler'])
@pytest.mark.parametrize('kind,stop', CASES)
async def test_sdk_uncertainty_keeps_secondary_diagnostic_and_exchange(tmp_path, stage, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [stage, kind, stop], record_property)
    assert (data['stage'], data['kind'], data['stop']) == (stage, kind, stop)
    assert data['caller_cancel_requests'] == {'none': 0, 'cancel': 2, 'timeout': 1}[stop]
    assert data['primary_identity'] and data['original_read_cause_context']
    assert data['native_secondary_identity'] is (None if kind == 'success' else True)
    assert data['native_secondary_cause_identity'] is (None if kind == 'success' else True)
    assert data['secondary_type'] == (kind if kind != 'success' else 'CancelledError' if stop != 'none' else None)
    assert data['native_sinks_settled'] and data['task_settled_before_emergency']
    assert data['handler_closed_before_return'] and data['logging_binding_restored']
    assert data['request_retained'] and data['result_absent'] and data['lifetime']['cleanup_confirmed']
    assert all(row['status'] in {'absent', 'reused'} for row in data['processes_before_release'].values())
    assert await asyncio.to_thread(Path(data['exchange_retained']).is_dir)
    expected = await asyncio.to_thread(lambda: {
        'path': str(Path(sdk_workload_runner.__file__).resolve()),
        'sha256': hashlib.sha256(Path(sdk_workload_runner.__file__).read_bytes()).hexdigest()})
    assert data['source_origins'][sdk_workload_runner.__name__] == expected
