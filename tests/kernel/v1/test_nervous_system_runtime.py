from __future__ import annotations

import pytest

from orket.kernel.v1.nervous_system_contract import GENESIS_STATE_DIGEST
from orket.kernel.v1.nervous_system_runtime import (
    admit_proposal_v1,
    commit_proposal_v1,
    end_session_v1,
    projection_pack_v1,
)
from orket.kernel.v1.nervous_system_runtime_extensions import get_session_ledger_events_v1


def _base_request(*, session_id: str, trace_id: str) -> dict[str, str]:
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
    }


@pytest.fixture(autouse=True)
def _enable_nervous_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")


def test_projection_pack_uses_genesis_when_session_has_no_head() -> None:
    response = projection_pack_v1(
        {
            **_base_request(session_id="sess-proj-a", trace_id="trace-proj-a"),
            "purpose": "action_path",
            "tool_context_summary": {"tool": "write_file"},
            "policy_context": {"mode": "strict"},
        }
    )
    assert response["contract_version"] == "kernel_api/v1"
    assert response["canonical_state_digest"] == GENESIS_STATE_DIGEST
    assert isinstance(response["projection_pack_digest"], str) and len(response["projection_pack_digest"]) == 64
    assert isinstance(response["event_digest"], str) and len(response["event_digest"]) == 64


def test_admit_proposal_orders_reason_codes_deterministically() -> None:
    response = admit_proposal_v1(
        {
            **_base_request(session_id="sess-admit-a", trace_id="trace-admit-a"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {
                    "approval_required_credentialed": True,
                    "approval_required_destructive": True,
                    "approval_required_exfil": True,
                },
            },
        }
    )
    assert response["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert response["admission_decision"]["reason_codes"] == [
        "APPROVAL_REQUIRED_DESTRUCTIVE",
        "APPROVAL_REQUIRED_EXFIL",
        "APPROVAL_REQUIRED_CREDENTIALED",
    ]


def test_admit_proposal_marks_exfil_from_tool_profile_flag() -> None:
    response = admit_proposal_v1(
        {
            **_base_request(session_id="sess-admit-exfil-a", trace_id="trace-admit-exfil-a"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"tool_profile": {"exfil": True}},
            },
        }
    )
    assert response["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert response["admission_decision"]["reason_codes"] == ["APPROVAL_REQUIRED_EXFIL"]


def test_admit_proposal_marks_exfil_from_non_local_target() -> None:
    response = admit_proposal_v1(
        {
            **_base_request(session_id="sess-admit-exfil-b", trace_id="trace-admit-exfil-b"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"target": "https://api.example.com/v1/send"},
            },
        }
    )
    assert response["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert response["admission_decision"]["reason_codes"] == ["APPROVAL_REQUIRED_EXFIL"]


def test_admit_proposal_does_not_mark_local_path_as_exfil() -> None:
    response = admit_proposal_v1(
        {
            **_base_request(session_id="sess-admit-exfil-c", trace_id="trace-admit-exfil-c"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"target": "agent_output/main.py"},
            },
        }
    )
    assert response["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"
    assert response["admission_decision"]["reason_codes"] == []


def test_commit_rejects_without_prior_admission() -> None:
    response = commit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-a", trace_id="trace-commit-a"),
            "proposal_digest": "a" * 64,
            "admission_decision_digest": "b" * 64,
            "execution_result_digest": "c" * 64,
        }
    )
    assert response["status"] == "REJECTED_PRECONDITION"


def test_commit_enforces_approval_id_for_needs_approval_decision() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-b", trace_id="trace-commit-b"),
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": {"approval_required_destructive": True},
            },
        }
    )

    response = commit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-b", trace_id="trace-commit-b"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "d" * 64,
        }
    )
    assert response["status"] == "REJECTED_APPROVAL_MISSING"


def test_commit_rejects_when_admission_exists_only_in_different_session() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-session-a", trace_id="trace-commit-session-a"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )
    response = commit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-session-b", trace_id="trace-commit-session-b"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "d" * 64,
        }
    )
    assert response["status"] == "REJECTED_PRECONDITION"


def test_commit_is_idempotent_for_identical_tuple() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-c", trace_id="trace-commit-c"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )
    payload = {
        **_base_request(session_id="sess-commit-c", trace_id="trace-commit-c"),
        "proposal_digest": admitted["proposal_digest"],
        "admission_decision_digest": admitted["decision_digest"],
        "execution_result_digest": "e" * 64,
    }
    first = commit_proposal_v1(payload)
    second = commit_proposal_v1(payload)
    assert first["status"] == "COMMITTED"
    assert second == first


def test_commit_with_digest_only_does_not_narrate_execution() -> None:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-digest-only", trace_id="trace-commit-digest-only"),
            "proposal": {"proposal_type": "action.tool_call", "payload": {}},
        }
    )

    response = commit_proposal_v1(
        {
            **_base_request(session_id="sess-commit-digest-only", trace_id="trace-commit-digest-only"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "f" * 64,
        }
    )

    assert response["status"] == "COMMITTED"
    event_types = {
        str(event.get("event_type") or "")
        for event in get_session_ledger_events_v1("sess-commit-digest-only")
    }
    assert "commit.recorded" in event_types
    assert "action.executed" not in event_types
    assert "action.result_validated" not in event_types


def test_end_session_emits_ended_status_and_event_digest() -> None:
    response = end_session_v1(
        {
            **_base_request(session_id="sess-end-a", trace_id="trace-end-a"),
            "reason": "test-complete",
        }
    )
    assert response["status"] == "ENDED"
    assert isinstance(response["event_digest"], str) and len(response["event_digest"]) == 64


def test_projection_pack_fails_when_feature_flag_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ORKET_ENABLE_NERVOUS_SYSTEM", raising=False)
    with pytest.raises(ValueError):
        projection_pack_v1(
            {
                **_base_request(session_id="sess-flag-off", trace_id="trace-flag-off"),
                "purpose": "action_path",
                "tool_context_summary": {},
                "policy_context": {},
            }
        )
