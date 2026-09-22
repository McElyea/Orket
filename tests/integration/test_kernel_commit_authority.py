"""Layer: integration. Retained Kernel admission and exact approval identity gate commit publication."""

import pytest

from orket.kernel.v1 import nervous_system_runtime as runtime
from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1.nervous_system_approvals import create_approval_request
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("credential_runtime")]


def test_returned_rejection_cannot_be_edited_to_authorize_credential_or_commit():
    admitted, request = admitted_request(policy_forbidden=True)
    admitted["admission_decision"]["decision"] = "ACCEPT_TO_UNIFY"
    admitted["admission_decision"]["reason_codes"].clear()
    with pytest.raises(ValueError):
        extensions.issue_credential_token_v1(request)
    result = runtime.commit_proposal_v1({**request, "canonical_state_digest_after": "unauthorized-state"})
    assert result["status"] == "REJECTED_POLICY"
    assert state.get_current_canonical_state_digest(request["session_id"]) != "unauthorized-state"
    assert state._TOKENS_BY_HASH == {}


@pytest.mark.parametrize("foreign", ["session", "proposal", "decision"])
def test_foreign_approved_record_cannot_authorize_commit_or_canonical_state(foreign):
    first, request = admitted_request(approval_required_credentialed=True)
    second, _ = admitted_request(
        session="foreign-session" if foreign == "session" else request["session_id"],
        target="foreign-target" if foreign == "proposal" else "first",
        approval_required_credentialed=True,
    )
    if foreign == "decision":
        second = create_approval_request(
            session_id=request["session_id"],
            trace_id=request["trace_id"],
            request_id=None,
            proposal_digest=request["proposal_digest"],
            decision_digest="different-decision",
            reason_codes=["APPROVAL_REQUIRED"],
        )
    assert first["approval_id"] != second["approval_id"]
    extensions.decide_approval_v1(
        approval_id=second["approval_id"], decision="approve", edited_proposal=None, notes=None
    )
    before = state.get_current_canonical_state_digest(request["session_id"])
    result = runtime.commit_proposal_v1(
        {**request, "approval_id": second["approval_id"], "canonical_state_digest_after": "unauthorized-state"}
    )
    assert result["status"] == "REJECTED_APPROVAL_MISSING"
    assert state.get_current_canonical_state_digest(request["session_id"]) == before
    (recorded,) = [
        row for row in state.list_events_for_session(request["session_id"]) if row["event_type"] == "commit.recorded"
    ]
    assert recorded["body"]["status"] == "REJECTED_APPROVAL_MISSING"
