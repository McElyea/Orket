"""Layer: integration. Concurrent actual commits have one retained publication."""

import asyncio
import sys
import threading

import pytest

from orket.kernel.v1.nervous_system_runtime import commit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_state import list_events_for_session
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


async def test_same_key_concurrent_commit_retains_exactly_one_event(monkeypatch):
    _, request = admitted_request()
    request.update(
        execution_result_digest="b" * 64,
        execution_result_payload={"ok": True},
        canonical_state_digest_after="committed-state",
    )
    module = sys.modules[commit_proposal_v1.__module__]
    entered, release, second_started = threading.Event(), threading.Event(), threading.Event()
    original = module.find_leak_hits

    def held(value):
        if not entered.is_set():
            entered.set()
            assert release.wait(10), "commit validation fixture not released"
        return original(value)

    def second_call():
        second_started.set()
        return commit_proposal_v1(request)

    monkeypatch.setattr(module, "find_leak_hits", held)
    first = asyncio.create_task(asyncio.to_thread(commit_proposal_v1, request))
    second = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 10)
        second = asyncio.create_task(asyncio.to_thread(second_call))
        assert await asyncio.wait_for(asyncio.to_thread(second_started.wait, 10), 10)
        await asyncio.sleep(0.1)
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([second] if second else [])), 10)
    assert len(results) == 2 and results[0] == results[1]
    assert results[0]["status"] == "COMMITTED" and results[0]["canonical_state_digest"] == "committed-state"
    assert (
        len([row for row in list_events_for_session(request["session_id"]) if row["event_type"] == "commit.recorded"])
        == 1
    )
