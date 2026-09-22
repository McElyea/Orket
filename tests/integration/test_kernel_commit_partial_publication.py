"""Layer: integration. Commit publication failure exposes partial state and releases its lock."""
import asyncio
import sys

import pytest

from orket.kernel.v1.nervous_system_runtime import commit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_state import get_current_canonical_state_digest, list_events_for_session
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


@pytest.mark.parametrize("after_event", [False, True], ids=["before-event", "after-event"])
async def test_failed_commit_publication_does_not_claim_rollback_or_cache(monkeypatch, after_event):
    _, request = admitted_request()
    request.update(canonical_state_digest_after="partial-state")
    owner = sys.modules[commit_proposal_v1.__module__]
    original = owner.append_event

    def fail(**kwargs):
        if after_event:
            original(**kwargs)
        raise OSError("controlled-publication-failure")

    monkeypatch.setattr(owner, "append_event", fail)
    with pytest.raises(OSError, match="controlled-publication-failure"):
        await asyncio.wait_for(asyncio.to_thread(commit_proposal_v1, request), 10)
    # Independent worker observation proves the failed owner released its actual RLock.
    canonical = await asyncio.wait_for(asyncio.to_thread(get_current_canonical_state_digest, request["session_id"]), 10)
    events = await asyncio.wait_for(asyncio.to_thread(list_events_for_session, request["session_id"]), 10)
    assert canonical == "partial-state"
    assert len([row for row in events if row["event_type"] == "commit.recorded"]) == int(after_event)
    monkeypatch.setattr(owner, "append_event", original)
    retried = await asyncio.wait_for(asyncio.to_thread(commit_proposal_v1, request), 10)
    assert retried["status"] == "COMMITTED"
    assert len([row for row in list_events_for_session(request["session_id"])
                if row["event_type"] == "commit.recorded"]) == 1 + int(after_event)
