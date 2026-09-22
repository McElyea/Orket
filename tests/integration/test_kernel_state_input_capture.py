"""Layer: integration. Actual Kernel hashing and validation retain one owned request."""

import asyncio
import threading
from copy import deepcopy

import pytest

from orket.kernel.v1 import nervous_system_runtime as runtime
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1.canonical import digest_of
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


async def test_admission_retains_the_proposal_used_by_actual_digest(monkeypatch):
    request = dict(
        contract_version="kernel_api/v1",
        session_id="captured-admit",
        trace_id="trace",
        proposal={"proposal_type": "action.tool_call", "payload": {"target": "first"}},
    )
    expected = digest_of(deepcopy(request["proposal"]))
    original = runtime.digest_of
    entered, release = threading.Event(), threading.Event()

    def hash_and_hold(payload):
        result = original(payload)
        if isinstance(payload, dict) and "proposal_type" in payload:
            entered.set()
            assert release.wait(10), "admission hash fixture was not released"
        return result

    monkeypatch.setattr(runtime, "digest_of", hash_and_hold)
    task = asyncio.create_task(asyncio.to_thread(runtime.admit_proposal_v1, request))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 11)
        request["proposal"]["payload"]["policy_forbidden"] = True
    finally:
        release.set()
        result = await asyncio.wait_for(task, 10)
    assert result["proposal_digest"] == expected
    assert result["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
    (event,) = [
        row for row in state.list_events_for_session(request["session_id"]) if row["event_type"] == "admission.decided"
    ]
    assert event["body"]["decision"] == "ACCEPT_TO_UNIFY"


async def test_commit_retains_observations_before_validation_wait(monkeypatch):
    import sys

    _, request = admitted_request()
    request.update(execution_result_schema_valid=True, canonical_state_digest_after="captured-state")
    owner = sys.modules[runtime.commit_proposal_v1.__module__]
    original = owner.get_str
    entered, release = threading.Event(), threading.Event()

    def validate_and_hold(payload, key, **kwargs):
        result = original(payload, key, **kwargs)
        if key == "session_id" and not entered.is_set():
            entered.set()
            assert release.wait(10), "commit validation fixture was not released"
        return result

    monkeypatch.setattr(owner, "get_str", validate_and_hold)
    task = asyncio.create_task(asyncio.to_thread(runtime.commit_proposal_v1, request))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 11)
        request.update(execution_result_schema_valid=False, canonical_state_digest_after="mutated-state")
    finally:
        release.set()
        result = await asyncio.wait_for(task, 10)
    assert result["status"] == "COMMITTED"
    assert result["canonical_state_digest"] == "captured-state"
