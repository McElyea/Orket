from __future__ import annotations

import pytest

from orket.kernel.v1.nervous_system_runtime import admit_proposal_v1
from orket.kernel.v1.nervous_system_runtime_state import reset_runtime_state_for_tests


@pytest.fixture(autouse=True)
def _enable_nervous_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_ENABLE_NERVOUS_SYSTEM", "true")
    reset_runtime_state_for_tests()


def _admit(monkeypatch: pytest.MonkeyPatch, *, session_id: str, trace_id: str, payload: dict, allow_flags: bool, use_resolver: bool) -> dict:
    monkeypatch.setenv("ORKET_ALLOW_PRE_RESOLVED_POLICY_FLAGS", "true" if allow_flags else "false")
    monkeypatch.setenv("ORKET_USE_TOOL_PROFILE_RESOLVER", "true" if use_resolver else "false")
    return admit_proposal_v1(
        {
            "contract_version": "kernel_api/v1",
            "session_id": session_id,
            "trace_id": trace_id,
            "proposal": {
                "proposal_type": "action.tool_call",
                "payload": payload,
            },
        }
    )


@pytest.mark.parametrize(
    ("payload", "expected_decision", "expected_reasons"),
    [
        (
            {
                "tool_name": "fs.delete",
                "args": {"path": "./workspace/important.txt"},
                "scope_violation": True,
            },
            "REJECT",
            ["SCOPE_VIOLATION"],
        ),
        (
            {
                "tool_name": "fs.write_patch",
                "args": {"path": "./workspace/notes.md", "patch": "ADD LINE hello"},
                "approval_required_destructive": True,
            },
            "NEEDS_APPROVAL",
            ["APPROVAL_REQUIRED_DESTRUCTIVE"],
        ),
        (
            {
                "tool_name": "demo.credentialed_echo",
                "args": {"credential_alias": "demo_secret", "message": "hello"},
                "approval_required_credentialed": True,
            },
            "NEEDS_APPROVAL",
            ["APPROVAL_REQUIRED_CREDENTIALED"],
        ),
    ],
)
def test_resolver_mode_matches_pre_resolved_flag_mode(
    monkeypatch: pytest.MonkeyPatch,
    payload: dict,
    expected_decision: str,
    expected_reasons: list[str],
) -> None:
    baseline = _admit(
        monkeypatch,
        session_id="sess-parity-a",
        trace_id="trace-parity-a",
        payload=payload,
        allow_flags=True,
        use_resolver=False,
    )
    resolved = _admit(
        monkeypatch,
        session_id="sess-parity-b",
        trace_id="trace-parity-b",
        payload=payload,
        allow_flags=False,
        use_resolver=True,
    )

    assert baseline["admission_decision"]["decision"] == expected_decision
    assert resolved["admission_decision"]["decision"] == expected_decision
    assert baseline["admission_decision"]["reason_codes"] == expected_reasons
    assert resolved["admission_decision"]["reason_codes"] == expected_reasons


def test_fail_closed_when_pre_resolved_flags_disabled_and_resolver_off(monkeypatch: pytest.MonkeyPatch) -> None:
    admitted = _admit(
        monkeypatch,
        session_id="sess-parity-closed",
        trace_id="trace-parity-closed",
        payload={"tool_name": "fs.write_patch", "args": {"path": "./workspace/notes.md"}},
        allow_flags=False,
        use_resolver=False,
    )
    assert admitted["admission_decision"]["decision"] == "NEEDS_APPROVAL"
    assert admitted["admission_decision"]["reason_codes"] == ["UNKNOWN_TOOL_PROFILE"]
