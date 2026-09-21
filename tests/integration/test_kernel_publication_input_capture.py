"""Actual SQLite publication retains the inputs admitted before its first wait."""
import asyncio
import json

import aiosqlite
import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.core.domain import ResultClass
from orket.kernel.v1.canonical import digest_of

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def publication_inputs():
    proposal = {'proposal_type': 'action.tool_call', 'payload': {'tool_name': 'demo.tool', 'args': {'value': ['original']}}}
    request = {'contract_version': 'kernel_api/v1', 'session_id': 'session', 'trace_id': 'trace',
        'proposal': proposal, 'proposal_digest': digest_of(proposal), 'admission_decision_digest': 'b' * 64}
    response = {'proposal_digest': request['proposal_digest'], 'decision_digest': 'b' * 64,
        'event_digest': 'c' * 64, 'admission_decision': {'decision': 'ACCEPT_TO_UNIFY'}}
    ledger = [{'event_type': 'admission.decided', 'created_at': '2026-09-20T12:00:00+00:00', 'event_digest': 'c' * 64}]
    return request, response, ledger


def hold_first_lookup(monkeypatch, repository):
    entered, release = asyncio.Event(), asyncio.Event()
    original = repository.get_run_record

    async def held(*, run_id):
        entered.set()
        await release.wait()
        return await original(run_id=run_id)

    monkeypatch.setattr(repository, 'get_run_record', held)
    return entered, release


async def stored_admission(database, run):
    async with aiosqlite.connect(database.as_uri() + '?mode=ro', uri=True) as connection:
        cursor = await connection.execute('SELECT payload_json FROM resolved_configuration_snapshots WHERE snapshot_id=?',
            (run.configuration_snapshot_id,))
        config = json.loads((await cursor.fetchone())[0])
        cursor = await connection.execute('SELECT payload_json FROM resolved_policy_snapshots WHERE snapshot_id=?',
            (run.policy_snapshot_id,))
        policy = json.loads((await cursor.fetchone())[0])
    return config, policy


@pytest.mark.parametrize('operation', ['admission', 'commit', 'session_end'])
async def test_kernel_publication_retains_request_response_and_ledger(tmp_path, monkeypatch, operation):
    database = tmp_path / 'kernel.sqlite3'
    execution = AsyncControlPlaneExecutionRepository(database)
    records = AsyncControlPlaneRecordRepository(database)
    service = KernelActionControlPlaneService(execution_repository=execution,
        publication=ControlPlanePublicationService(repository=records))
    request, response, ledger = publication_inputs()
    if operation != 'admission':
        await service.record_admission(request=request, response=response, ledger_items=ledger)
        response.update(status='REJECTED_POLICY', commit_event_digest='d' * 64, event_digest='d' * 64)
        ledger.append({'event_type': 'commit.recorded' if operation == 'commit' else 'session.ended',
            'created_at': '2026-09-20T12:00:01+00:00', 'event_digest': 'd' * 64})
    entered, release = hold_first_lookup(monkeypatch, execution)
    task = asyncio.create_task(getattr(service, 'record_' + operation)(request=request, response=response, ledger_items=ledger))
    try:
        await asyncio.wait_for(entered.wait(), timeout=10)
        request['proposal']['payload']['args']['value'][0] = 'rotated'
        request['execution_result_payload'] = {'claimed': 'after-admission'}
        request['execution_result_digest'] = 'e' * 64
        response['admission_decision']['decision'] = 'REJECT'
        response['status'] = 'COMMITTED'
        ledger[-1]['event_digest'] = '9' * 64
        ledger[-1]['created_at'] = '2026-09-20T12:00:20+00:00'
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)
    result = await task
    run, attempt = result[:2]
    if operation == 'admission':
        config, policy = await stored_admission(database, run)
        assert config['configuration_payload']['proposal']['payload']['args']['value'] == ['original']
        assert policy['policy_payload']['admission_decision'] == {'decision': 'ACCEPT_TO_UNIFY'}
        assert run.admission_decision_receipt_ref == 'kernel-admission-event:' + 'c' * 64
    elif operation == 'commit':
        assert result[2].result_class is ResultClass.BLOCKED
        assert result[3] is None and await records.list_effect_journal_entries(run_id=run.run_id) == []
        assert attempt.end_timestamp == '2026-09-20T12:00:01+00:00'
    else:
        assert attempt.end_timestamp == '2026-09-20T12:00:01+00:00'
        assert result[2].authoritative_result_ref == 'kernel-ledger-event:' + 'd' * 64
