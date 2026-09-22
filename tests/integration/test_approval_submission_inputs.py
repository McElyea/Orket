"""Integration: proposal submission retains arguments across actual storage waits."""
import asyncio
from datetime import datetime, timedelta

import pytest

from orket.core.domain.outward_authorization import canonical_json
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_authorization import hold_decision_writers, outward_api

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def admitted_service(client, context):
    response = await client.post('/v1/runs', json={
        'run_id': 'bt0-run', 'task': {'description': 'Captured proposal', 'instruction': 'wait'},
        'policy_overrides': {'approval_required_tools': ['write_file']},
    })
    assert response.status_code == 200 and response.json()['status'] == 'queued', response.text
    return context.outward_approval_service


def change_arguments(args):
    args['path'] = 'changed.json'
    args['content']['values'].append('changed')


async def verify_retained_proposal(context, proposal, expected, root):
    assert proposal.authorization.arguments_json == expected
    assert proposal.args_preview['path'] == 'admitted.json'
    assert proposal.authorization.target_ref == str(root / 'admitted.json')
    saved = await context.outward_approval_store.get(proposal.proposal_id)
    assert saved.authorization.arguments_json == expected
    run = await context.outward_run_store.get('bt0-run')
    assert run.status == 'approval_required' and run.pending_proposals[0]['args_preview']['path'] == 'admitted.json'
    events = await context.outward_run_event_store.list_for_run('bt0-run')
    pending = [event for event in events if event.event_type == 'proposal_pending_approval']
    assert len(pending) == 1 and pending[0].payload['args_preview']['path'] == 'admitted.json'
    assert not (root / 'admitted.json').exists() and not (root / 'changed.json').exists()


@pytest.mark.parametrize('mutation', ['arguments', 'clock'])
async def test_public_submission_captures_arguments_before_writer_wait(tmp_path, boundary, monkeypatch, mutation):
    db_path, inputs, _calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        service = await admitted_service(client, context)
        args = {'path': 'admitted.json', 'content': {'values': ['admitted']}}
        expected, task = canonical_json(args), None
        try:
            async with hold_decision_writers(db_path, monkeypatch, writers=1) as waiting:
                task = asyncio.create_task(service.request_tool_approval(
                    run_id='bt0-run', tool='write_file', args=args, context_summary='captured'))
                await asyncio.wait_for(waiting.wait(), 4)
                if mutation == 'arguments':
                    change_arguments(args)
                else:
                    inputs.now += timedelta(seconds=11)
            proposal = await asyncio.wait_for(task, 10)
            await verify_retained_proposal(context, proposal, expected, tmp_path)
            assert proposal.submitted_at == inputs.utc_now_iso()
            submitted = datetime.fromisoformat(proposal.submitted_at.replace('Z', '+00:00'))
            expires = datetime.fromisoformat(proposal.expires_at.replace('Z', '+00:00'))
            assert expires - submitted == timedelta(seconds=300)
        finally:
            if task is not None:
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize('operation', ['get_run', 'count_proposals'])
async def test_transaction_submission_captures_before_store_wait(tmp_path, boundary, monkeypatch, operation):
    _db_path, inputs, _calls = boundary
    async with outward_api(tmp_path, inputs) as (client, context):
        service = await admitted_service(client, context)
        args = {'path': 'admitted.json', 'content': {'values': ['admitted']}}
        expected = canonical_json(args)
        async with service.unit_of_work.transaction() as transaction:
            original = getattr(transaction, operation)
            entered, released = asyncio.Event(), asyncio.Event()

            async def held(*values):
                result = await original(*values)
                entered.set()
                await asyncio.wait_for(released.wait(), 5)
                return result

            monkeypatch.setattr(transaction, operation, held)
            task = asyncio.create_task(service.request_in_transaction(
                transaction, run_id='bt0-run', tool='write_file', args=args, context_summary='captured'))
            try:
                await asyncio.wait_for(entered.wait(), 4)
                change_arguments(args)
                released.set()
                proposal = await asyncio.wait_for(task, 10)
            finally:
                released.set()
                if not task.done():
                    task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        await verify_retained_proposal(context, proposal, expected, tmp_path)
