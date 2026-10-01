"""Integration: actual native process cleanup and physical lifetime-event append, isolated for fatal controls."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.adapters.observability import log_publication
from orket.application.services import command_process_supervisor, fixture_verification_service
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / 'helpers/lifetime_finalizer_worker.py'
CASES = [('success', 'none'), ('success', 'cancel'), ('success', 'timeout'),
    ('OSError', 'cancel'), ('TypeError', 'cancel'), ('CancelledError', 'cancel'),
    ('SystemExit', 'none'), ('SystemExit', 'cancel'), ('KeyboardInterrupt', 'none'), ('KeyboardInterrupt', 'cancel')]


@pytest.mark.parametrize('route', ['command', 'fixture'])
@pytest.mark.parametrize('kind,stop', CASES)
async def test_required_lifetime_finalizer_preserves_caller_policy(tmp_path, route, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [route, kind, stop], record_property)
    assert (data['route'], data['kind'], data['stop']) == (route, kind, stop)
    assert data['caller_cancel_requests'] == {'none': 1, 'cancel': 3, 'timeout': 2}[stop]
    assert data['native_calls'] == 1 and data['native_thread'] and data['native_settled']
    assert data['task_settled_before_emergency'] and not data['watchdog_expired']
    assert data['native_cause_identity'] is (None if kind == 'success' else True)
    assert data['fixture_primary_context_identity'] is (True if route == 'fixture' and kind != 'success' else None)
    assert data['command_failure_cause_identity'] is (True if route == 'command' and kind == 'OSError' else None)
    assert data['selected_cancel_identity'] == (kind == 'success' or (route == 'command' and kind == 'OSError'))
    assert data['domain_cancel_created'] == (route == 'fixture' or kind in {'success', 'OSError'})
    assert data['native_failure_identity'] == (kind != 'success' and not (route == 'command' and kind == 'OSError'))
    assert data['verification_result_unpublished'] is (True if route == 'fixture' else None)
    assert data['logging_binding_restored']
    lineage = data['live_lineage']['processes']
    assert lineage[0]['pid'] == data['live_lineage']['ready_pid']
    assert set(data['processes_before_release']) == {str(row['pid']) for row in lineage}
    assert all(data['processes_before_release'][str(row['pid'])]['expected_create_time'] == row['create_time']
               for row in lineage)
    assert all(item['status'] in {'absent', 'reused'} for item in data['processes_before_release'].values())
    for module in (command_process_supervisor, fixture_verification_service, log_publication):
        expected = await asyncio.to_thread(lambda selected=module: {
            'path': str(Path(selected.__file__).resolve()),
            'sha256': hashlib.sha256(Path(selected.__file__).read_bytes()).hexdigest()})
        assert data['source_origins'][module.__name__] == expected
