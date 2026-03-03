from __future__ import annotations

import pytest

from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1, commit_proposal_v1, end_session_v1
from orket.kernel.v1.nervous_system_runtime_extensions import (
    consume_credential_token_v1,
    decide_approval_v1,
    get_session_ledger_events_v1,
    issue_credential_token_v1,
    list_approvals_v1,
    rebuild_pending_approvals_v1,
)
from orket.kernel.v1.nervous_system_runtime_state import _PENDING_APPROVALS_CACHE, reset_runtime_state_for_tests


@pytest.fixture(autouse=True)
def _enable_nervous_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    reset_runtime_state_for_tests()


def _base_request(*, session_id: str, trace_id: str) -> dict[str, str]:
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
    }


def test_admit_needs_approval_creates_pending_approval_and_event() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-approval-a", trace_id="trace-approval-a"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )
    approval_id = admitted.get("approval_id")
    assert isinstance(approval_id, str) and approval_id

    items = list_approvals_v1(status="PENDING", session_id="sess-approval-a", request_id=None, limit=50)
    assert any(item["approval_id"] == approval_id for item in items)

    events = get_session_ledger_events_v1("sess-approval-a")
    assert any(event.get("event_type") == "approval.requested" for event in events)


def test_approval_decision_idempotent_and_conflict_behavior() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-approval-b", trace_id="trace-approval-b"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )
    approval_id = str(admitted["approval_id"])

    first = decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes="ok")
    assert first["status"] == "resolved"
    assert first["approval"]["status"] == "APPROVED"

    second = decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes="ok")
    assert second["status"] == "idempotent"

    with pytest.raises(RuntimeError):
        decide_approval_v1(approval_id=approval_id, decision="deny", edited_proposal=None, notes=None)


def test_approval_with_edits_creates_followup_admission_and_does_not_execute_original() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-approval-c", trace_id="trace-approval-c"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )

    decided = decide_approval_v1(
        approval_id=str(admitted["approval_id"]),
        decision="edit",
        edited_proposal={"target": "local/path.txt"},
        notes="narrow scope",
    )
    assert decided["status"] == "resolved"
    assert decided["approval"]["status"] == "APPROVED_WITH_EDITS"
    assert decided["next_admission"]["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"

    commit = commit_proposal_v1(
        {
            **_base_request(session_id="sess-approval-c", trace_id="trace-approval-c"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "approval_id": admitted["approval_id"],
            "execution_result_digest": "f" * 64,
        }
    )
    assert commit["status"] == "REJECTED_APPROVAL_MISSING"


def test_rebuild_pending_approvals_replays_ledger_as_source_of_truth() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-approval-d", trace_id="trace-approval-d"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )
    approval_id = str(admitted["approval_id"])

    _PENDING_APPROVALS_CACHE["sess-approval-d"] = []
    rebuilt = rebuild_pending_approvals_v1("sess-approval-d")
    assert len(rebuilt) == 1
    assert rebuilt[0]["approval_id"] == approval_id

    decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes=None)
    rebuilt_after = rebuild_pending_approvals_v1("sess-approval-d")
    assert rebuilt_after == []


def test_issue_and_consume_token_enforces_binding_and_replay_rules() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-token-a", trace_id="trace-token-a"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )

    issued = issue_credential_token_v1(
        {
            **_base_request(session_id="sess-token-a", trace_id="trace-token-a"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "tool_name": "send_email",
            "scope_json": {"allow": ["email.send"], "ttl_seconds": 60},
            "tool_profile_definition": {"tool": "send_email", "exfil": True, "risk": "high"},
        }
    )
    token = issued["token"]

    consumed = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-a", trace_id="trace-token-a"),
            "token": token,
            "proposal_digest": admitted["proposal_digest"],
            "tool_name": "send_email",
            "scope_json": {"ttl_seconds": 60, "allow": ["email.send"]},
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    assert consumed["ok"] is True

    replay = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-a", trace_id="trace-token-a"),
            "token": token,
            "proposal_digest": admitted["proposal_digest"],
            "tool_name": "send_email",
            "scope_json": {"allow": ["email.send"], "ttl_seconds": 60},
        }
    )
    assert replay["ok"] is False
    assert replay["reason_code"] == "TOKEN_REPLAY"


def test_issue_token_requires_approved_gate_for_needs_approval_admission() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-token-gated", trace_id="trace-token-gated"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_credentialed": True},
            },
        }
    )

    with pytest.raises(ValueError):
        issue_credential_token_v1(
            {
                **_base_request(session_id="sess-token-gated", trace_id="trace-token-gated"),
                "proposal_digest": admitted["proposal_digest"],
                "admission_decision_digest": admitted["decision_digest"],
                "tool_name": "send_email",
                "scope_json": {"allow": ["email.send"]},
                "tool_profile_definition": {"tool": "send_email", "exfil": True},
            }
        )

    decide_approval_v1(
        approval_id=str(admitted["approval_id"]),
        decision="approve",
        edited_proposal=None,
        notes=None,
    )
    issued = issue_credential_token_v1(
        {
            **_base_request(session_id="sess-token-gated", trace_id="trace-token-gated"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "approval_id": admitted["approval_id"],
            "tool_name": "send_email",
            "scope_json": {"allow": ["email.send"]},
            "tool_profile_definition": {"tool": "send_email", "exfil": True},
        }
    )
    assert isinstance(issued["token_id_hash"], str) and issued["token_id_hash"]


def test_token_replay_reason_code_drives_rejected_policy_commit() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-token-replay-commit", trace_id="trace-token-replay-commit"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_credentialed": True, "tool_name": "demo.credentialed_echo"},
            },
        }
    )
    decide_approval_v1(
        approval_id=str(admitted["approval_id"]),
        decision="approve",
        edited_proposal=None,
        notes=None,
    )
    issued = issue_credential_token_v1(
        {
            **_base_request(session_id="sess-token-replay-commit", trace_id="trace-token-replay-commit"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "approval_id": admitted["approval_id"],
            "tool_name": "demo.credentialed_echo",
            "scope_json": {"allow": ["credentialed_echo.use"]},
            "tool_profile_definition": {"tool": "demo.credentialed_echo", "exfil": False},
        }
    )

    first = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-replay-commit", trace_id="trace-token-replay-commit"),
            "token": issued["token"],
            "proposal_digest": admitted["proposal_digest"],
            "tool_name": "demo.credentialed_echo",
            "scope_json": {"allow": ["credentialed_echo.use"]},
        }
    )
    second = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-replay-commit", trace_id="trace-token-replay-commit"),
            "token": issued["token"],
            "proposal_digest": admitted["proposal_digest"],
            "tool_name": "demo.credentialed_echo",
            "scope_json": {"allow": ["credentialed_echo.use"]},
        }
    )
    assert first["ok"] is True
    assert second["ok"] is False
    assert second["reason_code"] == "TOKEN_REPLAY"

    committed = commit_proposal_v1(
        {
            **_base_request(session_id="sess-token-replay-commit", trace_id="trace-token-replay-commit"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "approval_id": admitted["approval_id"],
            "execution_result_digest": "9" * 64,
            "execution_error_reason_code": "TOKEN_REPLAY",
        }
    )
    assert committed["status"] == "REJECTED_POLICY"

    events = get_session_ledger_events_v1("sess-token-replay-commit")
    used_events = [event for event in events if event.get("event_type") == "credential.token_used"]
    assert len(used_events) == 1


def test_end_session_invalidates_active_tokens() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-token-b", trace_id="trace-token-b"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )
    issued = issue_credential_token_v1(
        {
            **_base_request(session_id="sess-token-b", trace_id="trace-token-b"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "tool_name": "send_email",
            "scope_json": {"allow": ["email.send"]},
            "tool_profile_definition": {"tool": "send_email", "exfil": True},
        }
    )

    ended = end_session_v1({**_base_request(session_id="sess-token-b", trace_id="trace-token-b"), "reason": "done"})
    assert ended["status"] == "ENDED"

    post_end = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-b", trace_id="trace-token-b"),
            "token": issued["token"],
            "proposal_digest": admitted["proposal_digest"],
            "tool_name": "send_email",
            "scope_json": {"allow": ["email.send"]},
        }
    )
    assert post_end["ok"] is False
    assert post_end["reason_code"] == "TOKEN_INVALID"


def test_admission_rejects_exfil_leak_and_emits_incident() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-leak-a", trace_id="trace-leak-a"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {
                    "target": "https://api.example.com/upload",
                    "outbound_payload": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
                },
            },
        }
    )
    assert admitted["admission_decision"]["decision"] == "REJECT"
    assert admitted["admission_decision"]["reason_codes"] == ["LEAK_DETECTED"]

    events = get_session_ledger_events_v1("sess-leak-a")
    incident_events = [event for event in events if event.get("event_type") == "incident.detected"]
    assert incident_events
    assert incident_events[-1]["body"]["stage"] == "admission"


def test_commit_blocks_leaky_result_when_configured() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-leak-b", trace_id="trace-leak-b"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )

    committed = commit_proposal_v1(
        {
            **_base_request(session_id="sess-leak-b", trace_id="trace-leak-b"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "a" * 64,
            "execution_result_payload": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "block_result_leaks": True,
        }
    )
    assert committed["status"] == "REJECTED_POLICY"


def test_commit_sanitizes_leaky_result_when_not_blocking() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-leak-c", trace_id="trace-leak-c"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )

    committed = commit_proposal_v1(
        {
            **_base_request(session_id="sess-leak-c", trace_id="trace-leak-c"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "b" * 64,
            "execution_result_payload": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----",
            "block_result_leaks": False,
        }
    )
    assert committed["status"] == "COMMITTED"
    assert isinstance(committed.get("sanitization_digest"), str)

    events = get_session_ledger_events_v1("sess-leak-c")
    assert any(event.get("event_type") == "action.result_validated" for event in events)
    assert any(event.get("event_type") == "incident.detected" for event in events)
