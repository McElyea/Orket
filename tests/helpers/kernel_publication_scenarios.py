"""Stable kernel publication scenarios executed against independent package versions."""
from copy import deepcopy

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.kernel_action_control_plane_service import KernelActionControlPlaneService
from orket.kernel.v1.canonical import digest_of


def publication_scenarios():
    variants = [{}, {'tool_name': 'local.echo', 'args': {'text': 'é', 'values': [True, None, 5]}},
        {'tool_name': 'fs.write_patch', 'args': {'path': './workspace/notes.md', 'patch': 'hello'}}]
    return [{'id': f'{operation}-{index}', 'operation': operation, 'payload': payload}
        for operation in ('admission', 'commit-rejected', 'commit-error', 'commit-success', 'session-end')
        for index, payload in enumerate(variants)]


async def observe_kernel_publication(case, database):
    execution = AsyncControlPlaneExecutionRepository(database)
    records = AsyncControlPlaneRecordRepository(database)
    service = KernelActionControlPlaneService(execution_repository=execution,
        publication=ControlPlanePublicationService(repository=records))
    proposal = {'proposal_type': 'action.tool_call', 'payload': deepcopy(case['payload'])}
    request = {'contract_version': 'kernel_api/v1', 'session_id': 'parity-session', 'trace_id': 'parity-trace',
        'proposal': proposal, 'proposal_digest': digest_of(proposal), 'admission_decision_digest': 'b' * 64}
    response = {'proposal_digest': request['proposal_digest'], 'decision_digest': 'b' * 64,
        'event_digest': 'c' * 64, 'admission_decision': {'decision': 'ACCEPT_TO_UNIFY', 'reason_codes': []}}
    ledger = [{'event_type': 'admission.decided', 'created_at': '2026-09-20T12:00:00+00:00', 'event_digest': 'c' * 64}]
    result = await service.record_admission(request=request, response=response, ledger_items=ledger)
    if case['operation'].startswith('commit-'):
        status = {'commit-rejected': 'REJECTED_POLICY', 'commit-error': 'ERROR', 'commit-success': 'COMMITTED'}[case['operation']]
        response.update(status=status, commit_event_digest='d' * 64)
        ledger.append({'event_type': 'commit.recorded', 'created_at': '2026-09-20T12:00:01+00:00', 'event_digest': 'd' * 64})
        if status == 'COMMITTED':
            request.update(execution_result_digest='e' * 64, execution_result_payload={'controlled': 'result'},
                execution_result_schema_valid=True)
        result = await service.record_commit(request=request, response=response, ledger_items=ledger)
    elif case['operation'] == 'session-end':
        response.update(status='ENDED', event_digest='d' * 64)
        ledger.append({'event_type': 'session.ended', 'created_at': '2026-09-20T12:00:01+00:00', 'event_digest': 'd' * 64})
        result = await service.record_session_end(request=request, response=response, ledger_items=ledger)
    run = result[0]
    policy = await records.get_resolved_policy_snapshot(snapshot_id=run.policy_snapshot_id)
    configuration = await records.get_resolved_configuration_snapshot(snapshot_id=run.configuration_snapshot_id)
    return {'result': [item.model_dump(mode='json') if item is not None else None for item in result],
        'policy': policy.model_dump(mode='json'), 'configuration': configuration.model_dump(mode='json')}
