from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.core.domain.guard_contract import (
    GuardContract,
    GuardViolation,
    LoopControl,
    LoopEscalation,
    TerminalReason,
)


def _strict_violation() -> GuardViolation:
    return GuardViolation(
        rule_id="TEST.RULE",
        code="TEST.FAIL",
        message="failure",
        location="output",
        severity="strict",
        evidence=None,
    )


def test_guard_contract_allows_pass_baseline():
    contract = GuardContract(
        result="pass",
        violations=[],
        severity="soft",
        fix_hint=None,
        terminal_failure=False,
        terminal_reason=None,
    )
    assert contract.result == "pass"
    assert contract.severity == "soft"


def test_guard_contract_rejects_pass_with_fix_hint():
    with pytest.raises(ValidationError):
        GuardContract(
            result="pass",
            violations=[],
            severity="soft",
            fix_hint="not allowed on pass",
            terminal_failure=False,
            terminal_reason=None,
        )


def test_guard_contract_rejects_terminal_failure_without_reason():
    with pytest.raises(ValidationError):
        GuardContract(
            result="fail",
            violations=[_strict_violation()],
            severity="strict",
            fix_hint="retry",
            terminal_failure=True,
            terminal_reason=None,
        )


def test_guard_contract_rejects_terminal_reason_without_terminal_failure():
    with pytest.raises(ValidationError):
        GuardContract(
            result="fail",
            violations=[_strict_violation()],
            fix_hint="retry",
            terminal_failure=False,
            terminal_reason=TerminalReason(code="X", message="terminal"),
        )


def test_guard_contract_aggregates_severity_from_violations():
    contract = GuardContract(
        result="fail",
        violations=[
            GuardViolation(
                rule_id="TEST.SOFT",
                code="TEST.SOFT",
                message="soft",
                location="output",
                severity="soft",
                evidence=None,
            ),
            _strict_violation(),
        ],
        severity="soft",
        fix_hint="retry",
        terminal_failure=False,
        terminal_reason=None,
    )
    assert contract.severity == "strict"


def test_loop_control_contract_model():
    control = LoopControl(
        max_retries=2,
        retry_backoff="linear",
        escalation=LoopEscalation(
            on_exceed="halt",
            terminal_reason=TerminalReason(code="HALLUCINATION_PERSISTENT", message="Repeated failures"),
        ),
    )
    assert control.max_retries == 2
    assert control.escalation.terminal_reason.code == "HALLUCINATION_PERSISTENT"
