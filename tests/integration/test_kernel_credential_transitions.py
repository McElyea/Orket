"""Layer: integration. Actual credential records/events, deterministic inputs and single use."""

import asyncio
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from orket.application.services.kernel_credential_input_service import capture_credential_observation
from orket.core.contracts.kernel_credentials import CredentialIssueInputs, CredentialObservation
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1 import nervous_system_tokens as tokens
from tests.helpers.kernel_credential_probe import admitted_request, consume_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("credential_runtime")]
NOW = datetime(2030, 1, 1, tzinfo=UTC)


def explicit_inputs():
    return CredentialIssueInputs(
        observed_at=NOW,
        hmac_key=b"explicit-fixture-key",
        raw_token="fixture-credential-value",
        token_id="tok-0123456789abcdef01234567",
    )


def test_explicit_issue_consume_and_event_time_ignore_later_environment(monkeypatch):
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs)
    monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "later-operator-value")
    observed = CredentialObservation(observed_at=NOW + timedelta(seconds=1), hmac_key=inputs.hmac_key)
    result = extensions.consume_credential_token_v1(consume_request(request, issued), inputs=observed)
    assert result["ok"]
    record = state._TOKENS_BY_HASH[issued["token_hash"]]
    events = [
        row
        for row in state.list_events_for_session(request["session_id"])
        if row["event_type"].startswith("credential.")
    ]
    assert record["used_at"] == record["invalidated_at"] == events[-1]["created_at"] == observed.observed_at.isoformat()
    assert events[0]["created_at"] == record["created_at"] == NOW.isoformat()
    exposed = json.dumps([record, events]) + repr(inputs)
    assert inputs.raw_token not in exposed and inputs.hmac_key.decode() not in exposed


@pytest.mark.parametrize("identity", ["token", "id"])
def test_identity_reuse_cannot_overwrite_a_used_credential(identity):
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs)
    assert extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)["ok"]
    again = (
        replace(inputs, token_id="different-id")
        if identity == "token"
        else replace(inputs, raw_token="different-token")
    )
    before = json.dumps(state._TOKENS_BY_HASH, sort_keys=True)
    events = state.list_events_for_session(request["session_id"])
    with pytest.raises(ValueError, match="E_CREDENTIAL_IDENTITY_REUSE"):
        extensions.issue_credential_token_v1(request, inputs=again)
    assert json.dumps(state._TOKENS_BY_HASH, sort_keys=True) == before
    assert state.list_events_for_session(request["session_id"]) == events
    assert (
        extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)["reason_code"]
        == "TOKEN_REPLAY"
    )


@pytest.mark.parametrize("kind", ["session", "proposal"])
def test_explicit_invalidation_retains_time_and_cannot_be_replayed(kind):
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs)
    observed = NOW + timedelta(seconds=5)
    arguments = dict(session_id=request["session_id"], reason="closed", observed_at=observed)
    if kind == "proposal":
        arguments["proposal_digest"] = request["proposal_digest"]
    assert getattr(tokens, "invalidate_tokens_for_" + kind)(**arguments) == 1
    assert (
        getattr(tokens, "invalidate_tokens_for_" + kind)(
            **{**arguments, "observed_at": observed + timedelta(seconds=5)}
        )
        == 0
    )
    assert state._TOKENS_BY_HASH[issued["token_hash"]]["invalidated_at"] == observed.isoformat()
    assert (
        extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)["reason_code"]
        == "TOKEN_INVALID"
    )


def test_between_invocation_key_rotation_and_explicit_empty_environment_remain_authoritative(monkeypatch):
    _, request = admitted_request()
    issued = extensions.issue_credential_token_v1(request)
    before = capture_credential_observation()
    monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "rotated-fixture-key")
    assert extensions.consume_credential_token_v1(consume_request(request, issued))["reason_code"] == "TOKEN_INVALID"
    assert extensions.consume_credential_token_v1(consume_request(request, issued), inputs=before)["ok"]
    assert capture_credential_observation(environment={}).hmac_key == b"orket-nervous-system-dev-hmac-key"


@pytest.mark.parametrize("operation", ["issue", "consume"])
def test_event_failure_remains_visible_without_resetting_credential_state(monkeypatch, operation):
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs) if operation == "consume" else None
    events = state.list_events_for_session(request["session_id"])

    def fail_event(**kwargs):
        raise OSError("fixture event publication failure")

    monkeypatch.setattr(extensions, "append_event", fail_event)
    with pytest.raises(OSError, match="fixture event publication failure"):
        if operation == "issue":
            extensions.issue_credential_token_v1(request, inputs=inputs)
        else:
            extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)
    assert state.list_events_for_session(request["session_id"]) == events
    assert len(state._TOKENS_BY_HASH) == 1
    record = next(iter(state._TOKENS_BY_HASH.values()))
    if operation == "issue":
        assert record["used_at"] is None
        with pytest.raises(ValueError, match="E_CREDENTIAL_IDENTITY_REUSE"):
            extensions.issue_credential_token_v1(request, inputs=inputs)
    else:
        assert record["used_at"] == record["invalidated_at"] == NOW.isoformat()
        assert (
            extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)["reason_code"]
            == "TOKEN_REPLAY"
        )


@pytest.mark.parametrize("condition", ["boundary", "malformed", "used_expired", "already_invalidated"])
def test_expiry_refusal_preserves_record_and_event_semantics(condition):
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs)
    record = state._TOKENS_BY_HASH[issued["token_hash"]]
    # Controlled existing-record faults exercise the actual public consume path.
    prior_time = (NOW - timedelta(seconds=1)).isoformat()
    if condition == "malformed":
        record["expires_at"] = "invalid stored timestamp"
    elif condition == "already_invalidated":
        record["invalidated_at"], record["invalidation_reason"] = prior_time, "expired"
    else:
        record["expires_at"] = NOW.isoformat()
        if condition == "used_expired":
            record["used_at"] = prior_time
    events = state.list_events_for_session(request["session_id"])
    result = extensions.consume_credential_token_v1(consume_request(request, issued), inputs=inputs)
    assert result == {"ok": False, "reason_code": "TOKEN_EXPIRED"}
    expected_time = prior_time if condition == "already_invalidated" else NOW.isoformat()
    assert record["invalidated_at"] == expected_time
    assert record["invalidation_reason"] == "expired"
    assert record["used_at"] == (prior_time if condition == "used_expired" else None)
    assert state.list_events_for_session(request["session_id"]) == events


@pytest.mark.asyncio
async def test_concurrent_native_threads_consume_exactly_once():
    _, request = admitted_request()
    inputs = explicit_inputs()
    issued = extensions.issue_credential_token_v1(request, inputs=inputs)
    outcomes = await asyncio.gather(
        *(
            asyncio.to_thread(extensions.consume_credential_token_v1, consume_request(request, issued), inputs=inputs)
            for _ in range(12)
        )
    )
    assert sum(result["ok"] for result in outcomes) == 1
    assert sum(result.get("reason_code") == "TOKEN_REPLAY" for result in outcomes) == 11
    assert (
        sum(
            row["event_type"] == "credential.token_used" for row in state.list_events_for_session(request["session_id"])
        )
        == 1
    )
