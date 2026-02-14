from __future__ import annotations

from orket.application.services.guard_agent import GuardAgent, GuardEvaluator, GuardController
from orket.core.domain.guard_contract import GuardContract, GuardViolation, TerminalReason


def _failing_contract() -> GuardContract:
    return GuardContract(
        result="fail",
        violations=[
            GuardViolation(
                rule_id="RUNTIME.FAIL",
                code="RUNTIME_VERIFIER_FAILED",
                message="failed",
                location="output",
                severity="strict",
                evidence="trace",
            )
        ],
        severity="strict",
        fix_hint="fix",
        terminal_failure=False,
        terminal_reason=None,
    )


def test_guard_agent_pass_result_continues_without_retry_change():
    contract = GuardContract(
        result="pass",
        violations=[],
        severity="soft",
        fix_hint=None,
        terminal_failure=False,
        terminal_reason=None,
    )
    decision = GuardAgent().evaluate(contract=contract, retry_count=1, max_retries=3)
    assert decision.action == "pass"
    assert decision.next_retry_count == 1
    assert decision.terminal_failure is False


def test_guard_agent_fail_result_schedules_retry_when_under_limit():
    decision = GuardAgent().evaluate(contract=_failing_contract(), retry_count=0, max_retries=2)
    assert decision.action == "retry"
    assert decision.next_retry_count == 1
    assert decision.terminal_failure is False
    assert decision.retry_fingerprint
    assert decision.repeated_fingerprint is False


def test_guard_agent_fail_result_becomes_terminal_when_limit_reached():
    decision = GuardAgent().evaluate(contract=_failing_contract(), retry_count=2, max_retries=2)
    assert decision.action == "terminal_failure"
    assert decision.terminal_failure is True
    assert decision.terminal_reason is not None
    assert decision.terminal_reason.code == "GUARD_RETRY_EXCEEDED"


def test_guard_agent_respects_contract_terminal_failure():
    contract = GuardContract(
        result="fail",
        violations=[
            GuardViolation(
                rule_id="HALLUCINATION.PERSISTENT",
                code="HALLUCINATION_PERSISTENT",
                message="persistent",
                location="output",
                severity="strict",
                evidence="repeat",
            )
        ],
        severity="strict",
        fix_hint="stop",
        terminal_failure=True,
        terminal_reason=TerminalReason(code="HALLUCINATION_PERSISTENT", message="repeat failure"),
    )
    decision = GuardAgent().evaluate(contract=contract, retry_count=0, max_retries=5)
    assert decision.action == "terminal_failure"
    assert decision.terminal_reason is not None
    assert decision.terminal_reason.code == "HALLUCINATION_PERSISTENT"


def test_guard_agent_uses_hallucination_persistent_on_retry_exceed():
    contract = GuardContract(
        result="fail",
        violations=[
            GuardViolation(
                rule_id="HALLUCINATION.FILE_NOT_FOUND",
                code="HALLUCINATION_FILE_NOT_FOUND",
                message="missing file",
                location="output",
                severity="strict",
                evidence="agent_output/missing.py",
            )
        ],
        severity="strict",
        fix_hint="scope",
        terminal_failure=False,
        terminal_reason=None,
    )
    decision = GuardAgent().evaluate(contract=contract, retry_count=2, max_retries=2)
    assert decision.action == "terminal_failure"
    assert decision.terminal_reason is not None
    assert decision.terminal_reason.code == "HALLUCINATION_PERSISTENT"


def test_guard_agent_repeated_retry_fingerprint_becomes_model_non_compliant():
    contract = _failing_contract()
    agent = GuardAgent()
    seen = []
    first = agent.evaluate(
        contract=contract,
        retry_count=0,
        max_retries=2,
        output_text="same failure output",
        seen_fingerprints=seen,
    )
    second = agent.evaluate(
        contract=contract,
        retry_count=1,
        max_retries=2,
        output_text="same failure output",
        seen_fingerprints=seen,
    )

    assert first.action == "retry"
    assert second.action == "terminal_failure"
    assert second.terminal_reason is not None
    assert second.terminal_reason.code == "MODEL_NON_COMPLIANT"
    assert second.repeated_fingerprint is True


def test_guard_evaluator_and_controller_split_contract_and_policy():
    contract = _failing_contract()
    evaluator = GuardEvaluator()
    controller = GuardController()
    evaluated = evaluator.evaluate_contract(contract=contract)
    decision = controller.decide(contract=evaluated, retry_count=0, max_retries=1, output_text="failed")
    assert decision.action == "retry"
