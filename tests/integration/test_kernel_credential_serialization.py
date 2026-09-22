"""Layer: integration. Real runtime RLock serializes admission observation through issuance."""
import asyncio
import threading
from functools import partial
from time import perf_counter

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.kernel.v1 import nervous_system_runtime as runtime
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1 import nervous_system_tokens as tokens
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


async def test_credential_publication_retains_admission_lock_through_actual_hashing(tmp_path, monkeypatch, record_property):
    admitted, request = admitted_request()
    entered, release, waiting = threading.Event(), threading.Event(), threading.Event()
    original_lock = state._RUNTIME_LOCK
    # Observe the exact .74 or current hashing function without replacing its result.
    name = "credential_hash" if hasattr(tokens, "credential_hash") else "_token_hash"
    original_hash = getattr(tokens, name)

    def hash_and_hold(*args):
        result = original_hash(*args)
        entered.set()
        assert release.wait(10), "credential hashing fixture not released"
        return result

    class ObservedLock:
        def __enter__(self):
            waiting.set()
            return original_lock.__enter__()

        def __exit__(self, *args):
            return original_lock.__exit__(*args)

    monkeypatch.setattr(tokens, name, hash_and_hold)
    monkeypatch.setattr(runtime, "_RUNTIME_LOCK", ObservedLock())
    first = asyncio.create_task(run_owned_thread(partial(extensions.issue_credential_token_v1, request), label="issue"))
    competing = None
    try:
        assert await asyncio.wait_for(asyncio.to_thread(entered.wait, 10), 11)
        monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "false")
        proposal = dict(contract_version="kernel_api/v1", session_id=request["session_id"], trace_id="later-trace",
                        proposal={"proposal_type": "action.tool_call", "payload": {"target": "first"}})
        competing = asyncio.create_task(run_owned_thread(partial(runtime.admit_proposal_v1, proposal), label="admit"))
        assert await asyncio.wait_for(asyncio.to_thread(waiting.wait, 10), 11)
        started = perf_counter()
        async with connect_sqlite_wal(tmp_path / "independent.db") as connection, connection.execute("SELECT 42") as cursor:
            assert await cursor.fetchone() == (42,)
        elapsed = perf_counter() - started
        assert elapsed < .5
        record_property("independent_sqlite_seconds", elapsed)
        await asyncio.sleep(.8)
        assert not competing.done(), "admission changed before credential publication finished"
    finally:
        release.set()
        results = await asyncio.wait_for(asyncio.gather(first, *([competing] if competing else [])), 10)
    assert results[1]["proposal_digest"] == admitted["proposal_digest"]
    assert results[1]["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    events = state.list_events_for_session(request["session_id"])
    issued_id = next(row["id"] for row in events if row["event_type"] == "credential.token_issued")
    later_id = next(row["id"] for row in events if row["event_type"] == "admission.decided" and row["trace_id"] == "later-trace")
    assert issued_id < later_id
