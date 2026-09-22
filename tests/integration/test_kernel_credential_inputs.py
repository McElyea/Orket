"""Layer: integration. Actual HMAC/records/events through held synchronous validation."""
import hashlib
import hmac
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from functools import partial

import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1 import nervous_system_tokens as tokens
from orket.kernel.v1.nervous_system_contract import canonical_scope_digest
from tests.helpers.kernel_credential_probe import CredentialValidationHold, admitted_request, consume_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("credential_runtime")]


@pytest.mark.parametrize("operation", ["issue", "consume"])
async def test_credential_key_is_captured_before_validation_observation(monkeypatch, operation):
    _, request = admitted_request()
    if operation == "consume":
        issued = extensions.issue_credential_token_v1(request)
        request = consume_request(request, issued)
    hold = CredentialValidationHold(monkeypatch)
    call = extensions.issue_credential_token_v1 if operation == "issue" else extensions.consume_credential_token_v1
    result = await hold.run(partial(call, request),
        lambda: monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "credential-fixture-after"))
    if operation == "issue":
        expected = hmac.new(b"credential-fixture-before", result["token"].encode(), hashlib.sha256).hexdigest()
        assert result["token_hash"] == expected
    else:
        assert result["ok"] is True
        assert state._TOKENS_BY_HASH[issued["token_hash"]]["used_at"] is not None


@pytest.mark.parametrize("operation", ["issue", "consume"])
async def test_credential_scope_is_owned_before_validation_observation(monkeypatch, operation):
    _, request = admitted_request()
    expected_scope = deepcopy(request["scope_json"])
    if operation == "consume":
        issued = extensions.issue_credential_token_v1(request)
        request = consume_request(request, issued)
    hold = CredentialValidationHold(monkeypatch)
    call = extensions.issue_credential_token_v1 if operation == "issue" else extensions.consume_credential_token_v1
    result = await hold.run(partial(call, request), lambda: request["scope_json"]["allow"].append("MUTATED"))
    if operation == "issue":
        assert result["scope_digest"] == canonical_scope_digest(expected_scope)
        assert state._TOKENS_BY_HASH[result["token_hash"]]["scope_json"] == expected_scope
    else:
        assert result["ok"] is True


async def test_credential_issue_uses_one_captured_time_for_expiry_record_and_event(monkeypatch):
    _, request = admitted_request()
    initial = datetime(2030, 1, 1, tzinfo=UTC)
    current = [initial]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0] if tz is not None else current[0].replace(tzinfo=None)

    # Clock sources are controlled; token HMAC, state publication and event hashes are real.
    monkeypatch.setattr(tokens, "datetime", Clock, raising=False)
    monkeypatch.setattr(state, "datetime", Clock)
    monkeypatch.setattr(RuntimeInputService, "utc_now", lambda self: current[0])
    hold = CredentialValidationHold(monkeypatch)
    issued = await hold.run(partial(extensions.issue_credential_token_v1, request),
        lambda: current.__setitem__(0, initial + timedelta(minutes=1)))
    assert issued["expires_at"] == (initial + timedelta(seconds=900)).isoformat()
    record = state._TOKENS_BY_HASH[issued["token_hash"]]
    event, = [row for row in state.list_events_for_session(request["session_id"])
              if row["event_type"] == "credential.token_issued"]
    assert record["created_at"] == event["created_at"] == initial.isoformat()
