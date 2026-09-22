"""Layer: integration. Default consumption reobserves expiry after real validation/lock waits."""
import asyncio
import threading
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1 import nervous_system_tokens as tokens
from tests.helpers.kernel_credential_probe import CredentialValidationHold, admitted_request, consume_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


@pytest.mark.parametrize("wait", ["validation", "lock"])
async def test_default_consume_refuses_expiry_reached_while_waiting(monkeypatch, wait):
    _, request = admitted_request()
    current = [datetime(2030, 1, 1, tzinfo=UTC)]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0] if tz is not None else current[0].replace(tzinfo=None)

    monkeypatch.setattr(tokens, "datetime", Clock, raising=False)
    monkeypatch.setattr(state, "datetime", Clock)
    monkeypatch.setattr(RuntimeInputService, "utc_now", lambda self: current[0])
    issued = extensions.issue_credential_token_v1({**request, "expires_in_seconds": 1})
    call = partial(extensions.consume_credential_token_v1, consume_request(request, issued))
    boundary = current[0] + timedelta(seconds=1)
    if wait == "validation":
        result = await CredentialValidationHold(monkeypatch).run(call, lambda: current.__setitem__(0, boundary))
    else:
        attempted = threading.Event()
        original = state._RUNTIME_LOCK

        class ObservedLock:
            def __enter__(self):
                attempted.set()
                return original.__enter__()

            def __exit__(self, *args):
                return original.__exit__(*args)

        monkeypatch.setattr(extensions, "_RUNTIME_LOCK", ObservedLock(), raising=False)
        monkeypatch.setattr(tokens, "_RUNTIME_LOCK", ObservedLock())
        with original:
            task = asyncio.create_task(asyncio.to_thread(call))
            assert await asyncio.wait_for(asyncio.to_thread(attempted.wait, 10), 11)
            current[0] = boundary
        result = await asyncio.wait_for(task, 10)
    assert result == {"ok": False, "reason_code": "TOKEN_EXPIRED"}
    record = state._TOKENS_BY_HASH[issued["token_hash"]]
    assert record["used_at"] is None
    assert record["invalidated_at"] == boundary.isoformat()
    assert all(row["event_type"] != "credential.token_used" for row in state.list_events_for_session(request["session_id"]))
