"""Layer: integration. Default consumption reobserves expiry after real validation/lock waits."""
import asyncio
import threading
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest

from orket.application.services.kernel_runtime_owner import current_kernel_runtime
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from tests.helpers.kernel_credential_probe import CredentialValidationHold, admitted_request, consume_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime
from tests.helpers.kernel_runtime import ObservedKernelLock, select_test_clock

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


@pytest.mark.parametrize("wait", ["validation", "lock"])
async def test_default_consume_refuses_expiry_reached_while_waiting(monkeypatch, wait):
    _, request = admitted_request()
    current = [datetime(2030, 1, 1, tzinfo=UTC)]

    select_test_clock(monkeypatch, lambda: current[0])
    issued = extensions.issue_credential_token_v1({**request, "expires_in_seconds": 1})
    call = partial(extensions.consume_credential_token_v1, consume_request(request, issued))
    boundary = current[0] + timedelta(seconds=1)
    if wait == "validation":
        result = await CredentialValidationHold(monkeypatch).run(call, lambda: current.__setitem__(0, boundary))
    else:
        attempted = threading.Event()
        original = current_kernel_runtime().lock

        monkeypatch.setattr(current_kernel_runtime(), "lock", ObservedKernelLock(original, attempted))
        with original:
            task = asyncio.create_task(asyncio.to_thread(call))
            assert await asyncio.wait_for(asyncio.to_thread(attempted.wait, 10), 11)
            current[0] = boundary
        result = await asyncio.wait_for(task, 10)
    assert result == {"ok": False, "reason_code": "TOKEN_EXPIRED"}
    record = current_kernel_runtime().tokens_by_hash[issued["token_hash"]]
    assert record["used_at"] is None
    assert record["invalidated_at"] == boundary.isoformat()
    assert all(row["event_type"] != "credential.token_used" for row in state.list_events_for_session(request["session_id"]))
