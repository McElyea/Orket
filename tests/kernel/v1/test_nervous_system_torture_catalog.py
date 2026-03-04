from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1, commit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_extensions import (
    consume_credential_token_v1,
    decide_approval_v1,
    get_session_ledger_events_v1,
    issue_credential_token_v1,
    rebuild_pending_approvals_v1,
)
from orket.kernel.v1.nervous_system_runtime_state import (
    _PENDING_APPROVALS_CACHE,
    _RUNTIME_LOCK,
    _TOKENS_BY_HASH,
    reset_runtime_state_for_tests,
)

CORPUS_PATH = Path("benchmarks/scenarios/nervous_system_attack_corpus.json")


def _load_corpus_cases() -> list[dict[str, Any]]:
    payload = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise AssertionError("attack corpus cases must be a list")
    return [dict(case) for case in cases if isinstance(case, dict)]


def _case_by_id(case_id: str) -> dict[str, Any]:
    for case in _load_corpus_cases():
        if str(case.get("id") or "") == case_id:
            return case
    raise AssertionError(f"case not found: {case_id}")


def _base_request(*, session_id: str, trace_id: str, request_id: str) -> dict[str, str]:
    return {
        "contract_version": "kernel_api/v1",
        "session_id": session_id,
        "trace_id": trace_id,
        "request_id": request_id,
    }


def _proposal_from_case(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_type": "action.tool_call",
        "payload": dict(case.get("payload") or {}),
    }


def _admission_cases() -> list[dict[str, Any]]:
    return _load_corpus_cases()


@pytest.fixture(autouse=True)
def _enable_nervous_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "false")
    reset_runtime_state_for_tests()


@pytest.mark.parametrize("case", _admission_cases(), ids=lambda case: str(case.get("id") or "case"))
def test_attack_catalog_admission_outcomes(case: dict[str, Any]) -> None:
    case_id = str(case.get("id") or "")
    expected = dict(case.get("expected") or {})
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id=f"sess-{case_id}", trace_id=f"trace-{case_id}", request_id=f"req-{case_id}"),
            "proposal": _proposal_from_case(case),
        }
    )

    assert admitted["admission_decision"]["decision"] == expected["admission_decision"]
    assert admitted["admission_decision"]["reason_codes"] == list(expected.get("reason_codes") or [])
    if admitted["admission_decision"]["decision"] == "NEEDS_APPROVAL":
        assert isinstance(admitted.get("approval_id"), str) and admitted["approval_id"]


def _issue_credential_token(case: dict[str, Any], *, session_id: str, trace_id: str) -> tuple[dict[str, Any], str]:
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id="req-token"),
            "proposal": _proposal_from_case(case),
        }
    )
    assert admitted["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    approval_id = str(admitted.get("approval_id") or "")
    decide_approval_v1(
        approval_id=approval_id,
        decision="approve",
        edited_proposal=None,
        notes="approve for token tests",
    )

    token_request = dict(case.get("token_request") or {})
    issued = issue_credential_token_v1(
        {
            **_base_request(session_id=session_id, trace_id=trace_id, request_id="req-token"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "approval_id": approval_id,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_definition": token_request["tool_profile_definition"],
            "expires_in_seconds": 60,
        }
    )
    return issued, admitted["proposal_digest"]


def test_token_scope_replay_and_expiry_fail_closed() -> None:
    case = _case_by_id("autonomy_credentialed_action_requires_approval")
    issued, proposal_digest = _issue_credential_token(
        case,
        session_id="sess-token-catalog",
        trace_id="trace-token-catalog",
    )
    token = issued["token"]
    token_request = dict(case["token_request"])

    wrong_scope = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-catalog", trace_id="trace-token-catalog", request_id="req-token"),
            "token": token,
            "proposal_digest": proposal_digest,
            "tool_name": token_request["tool_name"],
            "scope_json": {"allow": ["credentialed_echo.admin"]},
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    assert wrong_scope["ok"] is False
    assert wrong_scope["reason_code"] == "TOKEN_INVALID"

    first = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-catalog", trace_id="trace-token-catalog", request_id="req-token"),
            "token": token,
            "proposal_digest": proposal_digest,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    replay = consume_credential_token_v1(
        {
            **_base_request(session_id="sess-token-catalog", trace_id="trace-token-catalog", request_id="req-token"),
            "token": token,
            "proposal_digest": proposal_digest,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": issued["tool_profile_digest"],
        }
    )
    assert first["ok"] is True
    assert replay["ok"] is False
    assert replay["reason_code"] == "TOKEN_REPLAY"

    fresh, proposal_digest_fresh = _issue_credential_token(
        case,
        session_id="sess-token-expired-catalog",
        trace_id="trace-token-expired-catalog",
    )
    with _RUNTIME_LOCK:
        record = dict(_TOKENS_BY_HASH[fresh["token_hash"]])
        record["expires_at"] = "1970-01-01T00:00:00+00:00"
        _TOKENS_BY_HASH[fresh["token_hash"]] = record
    expired = consume_credential_token_v1(
        {
            **_base_request(
                session_id="sess-token-expired-catalog",
                trace_id="trace-token-expired-catalog",
                request_id="req-token",
            ),
            "token": fresh["token"],
            "proposal_digest": proposal_digest_fresh,
            "tool_name": token_request["tool_name"],
            "scope_json": token_request["scope_json"],
            "tool_profile_digest": fresh["tool_profile_digest"],
        }
    )
    assert expired["ok"] is False
    assert expired["reason_code"] == "TOKEN_EXPIRED"


def test_approval_fatigue_rebuilds_pending_queue_without_drift() -> None:
    session_id = "sess-approval-flood"
    case = _case_by_id("multi_step_benign_then_destructive_followup")
    payload = dict(case.get("payload") or {})

    approval_ids: list[str] = []
    for index in range(25):
        dynamic_payload = dict(payload)
        args = dict(dynamic_payload.get("args") or {})
        args["path"] = f"./workspace/notes_{index:02d}.md"
        dynamic_payload["args"] = args

        admitted = admit_proposal_v1(
            {
                **_base_request(
                    session_id=session_id,
                    trace_id=f"trace-approval-flood-{index:02d}",
                    request_id=f"req-{index:02d}",
                ),
                "proposal": {"proposal_type": "action.tool_call", "payload": dynamic_payload},
            }
        )
        assert admitted["admission_decision"]["decision"] == "NEEDS_APPROVAL"
        approval_ids.append(str(admitted["approval_id"]))

    assert len(set(approval_ids)) == 25
    _PENDING_APPROVALS_CACHE[session_id] = []
    rebuilt = rebuild_pending_approvals_v1(session_id)
    assert len(rebuilt) == 25
    rebuilt_ids = {str(item["approval_id"]) for item in rebuilt}
    assert rebuilt_ids == set(approval_ids)

    for approval_id in sorted(approval_ids)[:10]:
        decide_approval_v1(approval_id=approval_id, decision="approve", edited_proposal=None, notes="load-test")
    rebuilt_after = rebuild_pending_approvals_v1(session_id)
    assert len(rebuilt_after) == 15
    assert all(str(item["approval_id"]) not in set(sorted(approval_ids)[:10]) for item in rebuilt_after)


def test_result_disclosure_is_sanitized_and_not_logged_raw() -> None:
    case = _case_by_id("telemetry_secret_echo_requires_result_sanitization")
    case_id = str(case["id"])
    admitted = admit_proposal_v1(
        {
            **_base_request(session_id=f"sess-{case_id}", trace_id=f"trace-{case_id}", request_id=f"req-{case_id}"),
            "proposal": _proposal_from_case(case),
        }
    )
    assert admitted["admission_decision"]["decision"] == "ACCEPT_TO_UNIFY"

    committed = commit_proposal_v1(
        {
            **_base_request(session_id=f"sess-{case_id}", trace_id=f"trace-{case_id}", request_id=f"req-{case_id}"),
            "proposal_digest": admitted["proposal_digest"],
            "admission_decision_digest": admitted["decision_digest"],
            "execution_result_digest": "d" * 64,
            "execution_result_payload": str(case.get("result_payload") or ""),
            "block_result_leaks": False,
        }
    )
    assert committed["status"] == str(case["expected_commit_status"])
    assert isinstance(committed.get("sanitization_digest"), str)

    events = get_session_ledger_events_v1(f"sess-{case_id}")
    assert any(event.get("event_type") == "incident.detected" for event in events)
    raw_events = json.dumps(events, sort_keys=True)
    assert "ghp_abcdefghijklmnopqrstuvwxyz1234567890" not in raw_events
