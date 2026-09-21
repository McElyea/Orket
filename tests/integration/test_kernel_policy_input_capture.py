"""Actual kernel admission and in-memory events with controlled environment rotation."""
import asyncio
import threading
from functools import partial

import pytest

import orket.kernel.v1.nervous_system_runtime as runtime
from orket.adapters.execution.owned_io import run_owned_thread
from orket.kernel.v1 import api
from orket.kernel.v1.nervous_system_runtime_state import list_events_for_session, reset_runtime_state_for_tests

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize('resolver_enabled', [True, False])
async def test_admission_retains_operator_policy_during_proposal_hashing(monkeypatch, resolver_enabled):
    reset_runtime_state_for_tests()
    monkeypatch.setenv('ORKET_ENABLE_NERVOUS_SYSTEM', 'true')
    monkeypatch.setenv('ORKET_USE_TOOL_PROFILE_RESOLVER', str(resolver_enabled).lower())
    monkeypatch.setenv('ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS', str(not resolver_enabled).lower())
    request = {'contract_version': 'kernel_api/v1', 'session_id': 'policy-capture', 'trace_id': 'trace-capture',
        'proposal': {'proposal_type': 'action.tool_call', 'payload': {'tool_name': 'fs.delete',
            'args': {'path': './workspace/important.txt'}}}}
    entered, release = threading.Event(), threading.Event()
    digest = runtime.digest_of
    first = True

    def held_digest(value):
        nonlocal first
        if first:
            first = False
            entered.set()
            assert release.wait(5), 'Proposal hashing was not released'
        return digest(value)

    monkeypatch.setattr(runtime, 'digest_of', held_digest)
    operation = asyncio.create_task(run_owned_thread(partial(api.admit_proposal, request), label='kernel-policy-proof'))
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        monkeypatch.setenv('ORKET_USE_TOOL_PROFILE_RESOLVER', str(not resolver_enabled).lower())
        monkeypatch.setenv('ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS', str(resolver_enabled).lower())
        release.set()
        observed = await asyncio.wait_for(operation, 5)
        expected = {'decision': 'REJECT', 'reason_codes': ['SCOPE_VIOLATION']} if resolver_enabled else {
            'decision': 'ACCEPT_TO_UNIFY', 'reason_codes': []}
        assert observed['admission_decision'] == expected
        admitted, = [event for event in list_events_for_session('policy-capture') if event['event_type'] == 'admission.decided']
        assert admitted['body']['decision'] == expected['decision']
        assert admitted['body']['reason_codes'] == expected['reason_codes']
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
        reset_runtime_state_for_tests()
