"""Layer: integration. Explicit owners and selected inputs drive real Kernel chains."""

from datetime import UTC, datetime

import pytest

from orket.application.services.kernel_runtime_owner import KernelRuntime, current_kernel_runtime
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.kernel_credentials import credential_id_hash
from orket.core.contracts.kernel_observation import KernelObservation
from orket.kernel.v1 import nervous_system_runtime as runtime
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1.canonical import digest_of
from tests.helpers.kernel_credential_probe import consume_request
from tests.integration.test_kernel_runtime_isolation import kernel_enabled as kernel_enabled
from tests.integration.test_kernel_runtime_isolation import request

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("kernel_enabled")]
NOW = datetime(2030, 1, 1, tzinfo=UTC)


class SelectedInputs(RuntimeInputService):
    def utc_now(self):
        return NOW

    def create_secret_token(self):
        return "selected-fixture-secret"

    def create_credential_token_id(self):
        return "selected-fixture-token-id"


def unexpected_source():
    raise AssertionError("Kernel reread a replaced input port")


def run_chain():
    payload = request(approval_required_credentialed=True)
    projection = runtime.projection_pack_v1({**payload, "purpose": "action_path"})
    admitted = runtime.admit_proposal_v1(payload)
    extensions.decide_approval_v1(
        approval_id=admitted["approval_id"], decision="approve", edited_proposal=None, notes="selected fixture"
    )
    credential = {
        **payload,
        "proposal_digest": admitted["proposal_digest"],
        "admission_decision_digest": admitted["decision_digest"],
        "approval_id": admitted["approval_id"],
        "tool_name": "local.echo",
        "scope_json": {"allow": ["fixture.read"]},
        "tool_profile_definition": {"tool": "local.echo", "risk": "low"},
    }
    issued = extensions.issue_credential_token_v1(credential)
    assert issued["token"] == "selected-fixture-secret"
    assert extensions.consume_credential_token_v1(consume_request(credential, issued))["ok"]
    committed = runtime.commit_proposal_v1(
        {**credential, "execution_result_digest": "a" * 64, "canonical_state_digest_after": "selected-final-state"}
    )
    assert committed["status"] == "COMMITTED"
    ended = runtime.end_session_v1(payload)
    assert ended["canonical_state_digest"] == "selected-final-state"
    return projection, admitted, committed, ended, state.list_events_for_session(payload["session_id"])


def test_selected_ports_are_bound_once_and_produce_identical_real_chains(monkeypatch):
    monkeypatch.setenv("ORKET_NERVOUS_SYSTEM_TOKEN_HMAC_KEY", "selected-fixture-key")
    results = []
    for _ in range(2):
        selected = SelectedInputs()
        owner = KernelRuntime(runtime_inputs=selected)
        for name in ("utc_now", "create_secret_token", "create_credential_token_id"):
            monkeypatch.setattr(selected, name, unexpected_source)
        try:
            with owner.activate():
                results.append(run_chain())
                (token,) = owner.tokens_by_hash.values()
                assert token["token_id_hash"] == credential_id_hash("selected-fixture-token-id")
        finally:
            owner.close()
    assert results[0] == results[1]
    events = results[0][-1]
    assert len(events) >= 8 and {row["created_at"] for row in events} == {NOW.isoformat()}
    assert [row["id"] for row in events] == list(range(1, len(events) + 1))
    assert [row["prev_event_digest"] for row in events] == [None] + [row["event_digest"] for row in events[:-1]]
    for row in events:
        assert row["event_digest"] == digest_of({key: value for key, value in row.items() if key != "event_digest"})


def test_explicit_observations_override_selected_clock_for_decisions_and_events(monkeypatch):
    selected = SelectedInputs()
    monkeypatch.setattr(selected, "utc_now", unexpected_source)
    owner = KernelRuntime(runtime_inputs=selected)
    observed = KernelObservation(NOW)
    try:
        with owner.activate():
            payload = request(approval_required_credentialed=True)
            runtime.projection_pack_v1({**payload, "purpose": "action_path"}, observation=observed)
            admitted = runtime.admit_proposal_v1(payload, observation=observed)
            extensions.decide_approval_v1(
                approval_id=admitted["approval_id"],
                decision="approve",
                edited_proposal=None,
                notes=None,
                observation=observed,
            )
            committed = runtime.commit_proposal_v1(
                {
                    **payload,
                    "proposal_digest": admitted["proposal_digest"],
                    "admission_decision_digest": admitted["decision_digest"],
                    "approval_id": admitted["approval_id"],
                },
                observation=observed,
            )
            assert committed["status"] == "COMMITTED"
            assert runtime.end_session_v1(payload, observation=observed)["status"] == "ENDED"
            assert {row["created_at"] for row in state.list_events_for_session(payload["session_id"])} == {
                observed.timestamp
            }
    finally:
        owner.close()


def test_unbound_closed_and_nested_owners_cannot_share_context():
    with pytest.raises(RuntimeError, match="E_KERNEL_RUNTIME_OWNER_REQUIRED"):
        runtime.admit_proposal_v1(request())
    left, right = KernelRuntime(), KernelRuntime()
    try:
        with left.activate():
            runtime.admit_proposal_v1(request())
            with pytest.raises(ValueError, match="fixture abort"), right.activate():
                assert state.list_events_for_session("same-session") == []
                raise ValueError("fixture abort")
            assert current_kernel_runtime() is left
            assert len(state.list_events_for_session("same-session")) == 2
            left.close()
            with pytest.raises(RuntimeError, match="closed"):
                state.list_events_for_session("same-session")
        with pytest.raises(RuntimeError, match="closed"), left.activate():
            pytest.fail("closed owner admitted work")
        with pytest.raises(RuntimeError, match="E_KERNEL_RUNTIME_OWNER_REQUIRED"):
            current_kernel_runtime()
    finally:
        left.close()
        right.close()
