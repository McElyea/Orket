"""Integration: real guarded effects, native failure precedence and settled diagnostics."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path

import pytest

from orket.adapters.tools import runtime
from orket.application.services import card_workspace_mutation_service
from tests.integration.test_logging_preparation_lifetime import run_worker

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[1] / 'helpers/guarded_mutation_worker.py'
CASES = [('mutation', kind, stop) for kind in ('OSError', 'CancelledError', 'SystemExit', 'KeyboardInterrupt')
         for stop in ('none', 'cancel')]
CASES += [('tool', kind, stop) for kind in ('OSError', 'CancelledError', 'SystemExit', 'KeyboardInterrupt')
          for stop in ('cancel', 'deadline')]
CASES += [('mutation', 'success', 'cancel'), ('tool', 'success', 'none'), ('tool', 'success', 'deadline'),
          ('tool', 'success', 'deadline-repeated'), ('tool', 'BaseException', 'cancel')]
CASES += [(route, 'returned-exception', 'none') for route in ('mutation', 'tool')]
CASES += [('close', 'OSError', 'none'), ('close', 'OSError', 'cancel'), ('close', 'SystemExit', 'cancel')]


@pytest.mark.parametrize('route,kind,stop', CASES)
async def test_guarded_native_outcome_keeps_real_completion_exclusion(tmp_path, route, kind, stop, record_property):
    data = await run_worker(tmp_path, WORKER, [route, kind, stop], record_property)
    assert (data['route'], data['kind'], data['stop']) == (route, kind, stop)
    assert data['invoke_pending'] and data['competitor_pending'] and data['database_guard_held']
    assert data['native_finished'] and data['native_calls'] == 1
    assert data['outcome_policy'] and data['native_graph_preserved'] and data['real_completion_refused']
    assert data['healthy_followup'] and data['task_settled_before_emergency']
    expected = await asyncio.to_thread(lambda: {name: {'path': str(Path(module.__file__).resolve()),
        'sha256': hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()}
        for name, module in [('runtime', runtime), ('mutation', card_workspace_mutation_service)]})
    assert data['product_sources'] == expected


@pytest.mark.parametrize('kind', ['held', 'fatal'])
async def test_guarded_failure_diagnostic_settles_without_replacing_native_failure(tmp_path, kind, record_property):
    data = await run_worker(tmp_path, WORKER, ['diagnostic', kind, 'cancel'], record_property)
    assert data['route'] == 'diagnostic' and data['kind'] == kind
    assert data['handler_native'] and data['handler_calls'] == 1 and not data['watchdog_expired']
    assert data['native_primary_preserved'] and data['diagnostic_settled'] and data['task_settled_before_emergency']
    assert data['diagnostic_failed_marker'] is (kind == 'fatal')


@pytest.mark.parametrize('stop', ['cancel', 'deadline-repeated'])
async def test_custom_authority_still_receives_one_interruption_and_retains_cleanup(tmp_path, stop, record_property):
    data = await run_worker(tmp_path, WORKER, ['custom', 'success', stop], record_property)
    assert data['route'] == 'custom' and data['stop'] == stop
    assert data['one_authority_admission'] and data['one_forwarded_cancellation']
    assert data['cleanup_settled'] and data['task_settled_before_emergency']


@pytest.mark.parametrize('kind', ['task', 'future'])
async def test_invalid_authority_keeps_existing_caller_work_unadopted(tmp_path, kind, record_property):
    data = await run_worker(tmp_path, WORKER, ['refusal', kind, 'none'], record_property)
    assert data['route'] == 'refusal' and data['kind'] == kind
    assert data['rejected_without_adoption'] and data['actual_caller_work_retained']
    assert data['forbidden_tool_calls'] == 0
