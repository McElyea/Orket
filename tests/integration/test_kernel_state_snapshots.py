"""Layer: integration. Public Kernel observations cannot mutate retained authority or ledger bytes."""

from copy import deepcopy

import pytest

from orket.kernel.v1 import nervous_system_runtime_extensions as extensions
from orket.kernel.v1 import nervous_system_runtime_state as state
from orket.kernel.v1.canonical import digest_of
from tests.helpers.kernel_credential_probe import admitted_request
from tests.helpers.kernel_credential_probe import credential_runtime as credential_runtime

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("credential_runtime")]


@pytest.mark.parametrize("surface", ["input", "append", "list", "operator"])
def test_event_body_and_observations_are_detached_from_retained_history(surface):
    body = {"nested": {"values": ["original"]}}
    event = state.append_event(
        session_id="snapshot-session", trace_id="trace", event_type="fixture.observed", body=body
    )
    expected = deepcopy(event)
    if surface == "input":
        borrowed = body
    elif surface == "append":
        borrowed = event["body"]
    elif surface == "list":
        borrowed = state.list_events_for_session("snapshot-session")[0]["body"]
    else:
        borrowed = extensions.list_ledger_events_v1(session_id="snapshot-session")[0]["body"]
    borrowed["nested"]["values"].append("caller mutation")
    (actual,) = state.list_events_for_session("snapshot-session")
    assert actual == expected
    assert digest_of({key: value for key, value in actual.items() if key != "event_digest"}) == actual["event_digest"]


@pytest.mark.parametrize("surface", ["input", "decision", "get", "list", "ledger"])
def test_approval_resolution_is_not_borrowed_from_callers_or_observations(surface):
    admitted, request = admitted_request(approval_required_credentialed=True)
    edited = {"payload": {"target": ["original"]}}
    decided = extensions.decide_approval_v1(
        approval_id=admitted["approval_id"], decision="approve", edited_proposal=edited, notes="fixture"
    )
    expected = deepcopy(decided["approval"])
    events = deepcopy(state.list_events_for_session(request["session_id"]))
    if surface == "input":
        borrowed = edited
    elif surface == "decision":
        borrowed = decided["approval"]["resolution"]["edited_proposal"]
    elif surface == "get":
        borrowed = extensions.get_approval_v1(admitted["approval_id"])["resolution"]["edited_proposal"]
    elif surface == "list":
        rows = extensions.list_approvals_v1(status=None, session_id=request["session_id"], request_id=None, limit=20)
        borrowed = rows[0]["resolution"]["edited_proposal"]
    else:
        (event,) = [
            row
            for row in state.list_events_for_session(request["session_id"])
            if row["event_type"] == "approval.decided"
        ]
        borrowed = event["body"]["resolution"]["edited_proposal"]
    borrowed["payload"]["target"].append("caller mutation")
    assert extensions.get_approval_v1(admitted["approval_id"]) == expected
    assert state.list_events_for_session(request["session_id"]) == events


def test_pending_approval_observation_cannot_mutate_retained_reasons():
    admitted, request = admitted_request(approval_required_credentialed=True)
    expected = deepcopy(extensions.get_approval_v1(admitted["approval_id"]))
    rows = extensions.rebuild_pending_approvals_v1(request["session_id"])
    rows[0]["reason_codes"].append("CALLER_MUTATION")
    assert extensions.get_approval_v1(admitted["approval_id"]) == expected
