"""Layer: integration. Credential issue must retain the actual admitted authorization identity."""
import pytest

from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("credential_runtime")]


def test_rejected_admission_cannot_issue_credential():
    admitted, request = admitted_request(policy_forbidden=True)
    assert admitted["admission_decision"]["decision"] == "REJECT"
    with pytest.raises(ValueError):
        extensions.issue_credential_token_v1(request)
    assert state._TOKENS_BY_HASH == {}
    assert not any(row["event_type"] == "credential.token_issued"
                   for row in state.list_events_for_session(request["session_id"]))


@pytest.mark.parametrize("foreign", ["session", "proposal"])
def test_foreign_approved_record_cannot_authorize_credential(foreign):
    first, request = admitted_request(approval_required_credentialed=True)
    second, _ = admitted_request(session="other-session" if foreign == "session" else request["session_id"],
        target="other-target" if foreign == "proposal" else "first", approval_required_credentialed=True)
    assert first["approval_id"] != second["approval_id"]
    extensions.decide_approval_v1(approval_id=second["approval_id"], decision="approve", edited_proposal=None, notes=None)
    request["approval_id"] = second["approval_id"]
    with pytest.raises(ValueError):
        extensions.issue_credential_token_v1(request)
    assert state._TOKENS_BY_HASH == {}
    assert not any(row["event_type"] == "credential.token_issued"
                   for row in state.list_events_for_session(request["session_id"]))
