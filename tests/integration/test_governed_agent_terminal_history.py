"""Retained terminal claims must agree before inspection, replay or reentry."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace

import aiosqlite
import pytest
from fastapi.testclient import TestClient

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.storage.governed_agent_replay_store import GovernedAgentReplayStore
from orket.application.services.governed_agent_inspection_service import GovernedAgentInspectionService
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.application.services.governed_agent_replay_service import replay_governed_agent_evidence
from orket.core.domain import AttemptState, RunState
from orket.interfaces.runtime_entrypoints import create_api_app
from orket.runtime import CompositionConfig
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.integration.test_governed_agent_acceptance_failures import _run
from tests.interfaces.test_governed_agent_api import _configure_api, _headers
from tests.runtime.governed_agent_test_support import TEMPLATE_ROOT, agent_request, agent_workload_record

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("elapsed_agent_clock")]
CASES = ['coherent', 'unreferenced-truth', 'unfinished-attempt', 'wrong-reference',
         'missing-truth', 'failed-with-success', 'multiple-truths']


async def terminal_history(tmp_path, case):
    request = agent_request()
    source = await asyncio.to_thread((TEMPLATE_ROOT / 'governed_agent.py').read_text, encoding='utf-8')
    result, iterations = await _run(tmp_path, source, request)
    assert result.run.lifecycle_state is RunState.COMPLETED
    db = tmp_path / 'agent.sqlite3'
    await damage_terminal_history(db, result, case)
    return db, request, result, iterations


async def damage_terminal_history(db, result, case):
    execution = AsyncControlPlaneExecutionRepository(db)
    if case == 'unreferenced-truth':
        await execution.save_run_record(record=result.run.model_copy(update={
            'lifecycle_state': RunState.EXECUTING, 'final_truth_record_id': None,
        }))
    if case in {'unreferenced-truth', 'unfinished-attempt'}:
        await execution.save_attempt_record(record=result.attempt.model_copy(update={
            'attempt_state': AttemptState.EXECUTING, 'end_timestamp': None,
            'side_effect_boundary_class': None, 'failure_plane': None, 'failure_classification': None,
            'failure_class': None, 'recovery_decision_id': None,
        }))
    elif case == 'wrong-reference':
        await execution.save_run_record(record=result.run.model_copy(update={'final_truth_record_id': 'missing-truth'}))
    elif case == 'missing-truth':
        async with aiosqlite.connect(db) as conn:
            await conn.execute('DELETE FROM final_truth_records WHERE run_id = ?', (result.run.run_id,))
            await conn.commit()
    elif case == 'failed-with-success':
        await execution.save_run_record(record=result.run.model_copy(update={'lifecycle_state': RunState.FAILED_TERMINAL}))
        await execution.save_attempt_record(record=result.attempt.model_copy(update={'attempt_state': AttemptState.FAILED}))
    elif case == 'multiple-truths':
        duplicate = result.final_truth.model_copy(update={'final_truth_record_id': 'zz-conflicting-truth'})
        async with aiosqlite.connect(db) as conn:
            await conn.execute('INSERT INTO final_truth_records (final_truth_record_id, run_id, payload_json) VALUES (?, ?, ?)',
                               (duplicate.final_truth_record_id, duplicate.run_id, duplicate.model_dump_json()))
            await conn.commit()


async def logical_state(db):
    async with aiosqlite.connect(db) as conn:
        return tuple([line async for line in conn.iterdump()])


async def no_execution(**_kwargs):
    raise AssertionError('Terminal-history reentry must stop before invocation or verification.')


@pytest.mark.parametrize('surface', ['inspect', 'replay', 'reentry'])
@pytest.mark.parametrize('case', CASES)
# Layer: integration
async def test_retained_terminal_consistency_precedes_result_or_reentry(tmp_path, case, surface):
    db, request, completed, iterations = await terminal_history(tmp_path, case)
    before = await logical_state(db)
    execution = AsyncControlPlaneExecutionRepository(db)
    inspector = GovernedAgentInspectionService(
        iteration_repository=iterations, call_repository=iterations,
        replay_repository=GovernedAgentReplayStore(db),
    )
    if surface == 'replay':
        replay = await inspector.replay(run_id=completed.run.run_id)
        if case == 'coherent':
            assert replay['status'] == 'matched'
        else:
            assert replay['status'] != 'matched'
            assert replay['diagnostics']
    else:
        if surface == 'inspect':
            operation = inspector.inspect(run_id=completed.run.run_id)
        else:
            service = GovernedAgentLoopService(
                execution_repository=execution, iteration_repository=AsyncGovernedAgentRepository(db),
                transactions=SQLiteControlPlaneTransactions(db),
                invoker=SimpleNamespace(invoke_once=no_execution), verifier=SimpleNamespace(verify=no_execution),
            )
            now = datetime.fromisoformat(completed.run.creation_timestamp)
            operation = service.run_bounded(
                initial_request_payload=request, workload_record=agent_workload_record(),
                extension_digest='sha256:' + 'e' * 64, configuration_digest='sha256:' + 'c' * 64,
                admission_receipt_ref='agent-admission:test', creation_timestamp_utc=now.isoformat(),
                decision_timestamps_utc=[(now + timedelta(seconds=i)).isoformat() for i in range(2)],
                next_lease_expiries_utc=[request['lease_expires_at_utc']],
            )
        if case == 'coherent':
            observed = await operation
            assert (observed['final_truth']['result_class'] if surface == 'inspect'
                    else observed.final_truth.result_class.value) == 'success'
        else:
            with pytest.raises(ValueError, match='TERMINAL.*CONFLICT'):
                await operation
    assert await logical_state(db) == before


# Layer: integration
async def test_final_truth_identity_is_unique_for_the_retained_run(tmp_path):
    db, _, completed, _ = await terminal_history(tmp_path, 'coherent')
    records = AsyncControlPlaneRecordRepository(db)
    before = await logical_state(db)
    assert await records.save_final_truth(record=completed.final_truth) == completed.final_truth
    with pytest.raises(ValueError, match='FINAL_TRUTH.*CONFLICT'):
        await records.save_final_truth(record=completed.final_truth.model_copy(update={'final_truth_record_id': 'another-truth'}))
    assert await logical_state(db) == before


def public_history_observation(root, case):
    app = create_api_app(CompositionConfig(project_root=root))
    with TestClient(app) as client:
        route = '/v1/agent-runs/run-1'
        assert client.get(route).status_code == 403
        inspected = client.get(route, headers=_headers())
        assert inspected.status_code == (200 if case == 'coherent' else 409)
        replayed = client.get(route + '/replay', headers=_headers())
        assert replayed.status_code == 200
        assert (replayed.json()['status'] == 'matched') == (case == 'coherent')
        if case != 'coherent':
            assert 'E_AGENT_TERMINAL_AUTHORITY_CONFLICT' in inspected.json()['detail']
    assert app.state.api_runtime_context.closed


@pytest.mark.parametrize('case', ['coherent', 'unreferenced-truth', 'multiple-truths'])
# Layer: integration
async def test_api_reports_terminal_history_conflict_and_closes_owners(tmp_path, monkeypatch, case):
    db, _, _, _ = await terminal_history(tmp_path, case)
    _configure_api(monkeypatch, db, enabled=False)
    await asyncio.to_thread(public_history_observation, tmp_path, case)


WRITER = '''
import asyncio, json, sys
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.core.contracts import FinalTruthRecord
async def write():
    record = FinalTruthRecord.model_validate_json(sys.argv[2])
    try:
        await AsyncControlPlaneRecordRepository(sys.argv[1]).save_final_truth(record=record)
    except ValueError as exc:
        print(json.dumps({'status': 'conflict', 'error': str(exc)}))
    else:
        print(json.dumps({'status': 'accepted', 'id': record.final_truth_record_id}))
asyncio.run(write())
'''


# Layer: integration
async def test_native_writers_cannot_publish_two_terminal_identities(tmp_path):
    _, _, completed, _ = await terminal_history(tmp_path, 'coherent')
    db = tmp_path / 'competing.sqlite3'
    records = AsyncControlPlaneRecordRepository(db)
    assert await records.get_final_truth(run_id=completed.run.run_id) is None
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX='1')
    processes = []
    try:
        for identifier in ('truth-a', 'truth-b'):
            record = completed.final_truth.model_copy(update={'final_truth_record_id': identifier})
            processes.append(await asyncio.create_subprocess_exec(
                sys.executable, '-c', WRITER, str(db), record.model_dump_json(), env=environment,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            ))
        outputs = await asyncio.wait_for(asyncio.gather(*(child.communicate() for child in processes)), 20)
        assert all(child.returncode == 0 for child in processes), outputs
        rows = [json.loads(stdout) for stdout, _ in outputs]
        assert sorted(row['status'] for row in rows) == ['accepted', 'conflict']
        retained = await records.get_final_truth(run_id=completed.run.run_id)
        assert retained.final_truth_record_id == next(row['id'] for row in rows if row['status'] == 'accepted')
    finally:
        for child in processes:
            if child.returncode is None:
                child.kill()
        await asyncio.gather(*(child.wait() for child in processes))


# Layer: integration
async def test_agent_admission_does_not_retain_parent_after_attempt_write_failure(tmp_path, monkeypatch):
    db = tmp_path / 'admission.sqlite3'
    request = agent_request()
    execution = AsyncControlPlaneExecutionRepository(db)

    async def reject_attempt(_repository, *, record):
        raise RuntimeError('interrupted-attempt-admission')

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, 'save_attempt_record', reject_attempt)
    service = GovernedAgentLoopService(
        execution_repository=execution, iteration_repository=AsyncGovernedAgentRepository(db),
        transactions=SQLiteControlPlaneTransactions(db),
        invoker=SimpleNamespace(invoke_once=no_execution), verifier=SimpleNamespace(verify=no_execution),
    )
    with pytest.raises(RuntimeError, match='interrupted-attempt-admission'):
        await service.run_bounded(
            initial_request_payload=request, workload_record=agent_workload_record(),
            extension_digest='sha256:' + 'e' * 64, configuration_digest='sha256:' + 'c' * 64,
            admission_receipt_ref='agent-admission:test', creation_timestamp_utc='2026-09-14T00:00:00Z',
            decision_timestamps_utc=['2026-09-14T00:00:01Z', '2026-09-14T00:00:02Z'],
            next_lease_expiries_utc=[request['lease_expires_at_utc']],
        )
    assert await execution.get_run_record(run_id=request['identity']['run_id']) is None
    assert await execution.get_attempt_record(attempt_id=request['identity']['attempt_id']) is None


# Layer: integration
async def test_terminal_truth_cannot_bypass_replay_row_limit(tmp_path):
    db, _, completed, _ = await terminal_history(tmp_path, 'coherent')
    async with aiosqlite.connect(db) as connection:
        await connection.execute('UPDATE final_truth_records SET payload_json = payload_json || ?', (' ' * (64 * 1024 * 1024),))
        await connection.commit()
    before = await asyncio.to_thread(db.read_bytes)
    evidence = await GovernedAgentReplayStore(db).read_replay_evidence(run_id=completed.run.run_id)
    replay = replay_governed_agent_evidence(completed.run.run_id, evidence)
    assert replay['status'] == 'insufficient_evidence'
    assert replay['expected_count'] is None and replay['compared_count'] == 0
    assert 'replay_evidence_resource_limit' in replay['diagnostics']
    assert await asyncio.to_thread(db.read_bytes) == before
