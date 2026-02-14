from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal

from orket.core.domain.guard_contract import (
    GuardContract,
    LoopControl,
    LoopEscalation,
    TerminalReason,
)


GuardAction = Literal["pass", "retry", "terminal_failure"]


@dataclass(frozen=True)
class GuardDecision:
    action: GuardAction
    next_retry_count: int
    terminal_failure: bool
    terminal_reason: TerminalReason | None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "next_retry_count": self.next_retry_count,
            "terminal_failure": self.terminal_failure,
            "terminal_reason": (
                None if self.terminal_reason is None else self.terminal_reason.model_dump()
            ),
        }


class GuardAgent:
    """
    Non-generative guard evaluator.

    Evaluates GuardContract outcomes and returns deterministic loop decisions
    (pass/retry/terminal_failure) based on bounded retry policy.
    """

    def __init__(self, organization: Any = None):
        self.organization = organization

    def evaluate(
        self,
        *,
        contract: GuardContract,
        retry_count: int,
        max_retries: int,
    ) -> GuardDecision:
        if contract.result == "pass":
            return GuardDecision(
                action="pass",
                next_retry_count=retry_count,
                terminal_failure=False,
                terminal_reason=None,
            )

        if contract.terminal_failure:
            return GuardDecision(
                action="terminal_failure",
                next_retry_count=retry_count,
                terminal_failure=True,
                terminal_reason=contract.terminal_reason,
            )

        loop_control = self._resolve_loop_control(max_retries=max_retries)
        allowed_retries = max(0, min(int(max_retries), int(loop_control.max_retries)))
        if int(retry_count) < allowed_retries:
            return GuardDecision(
                action="retry",
                next_retry_count=int(retry_count) + 1,
                terminal_failure=False,
                terminal_reason=None,
            )

        return GuardDecision(
            action="terminal_failure",
            next_retry_count=int(retry_count),
            terminal_failure=True,
            terminal_reason=loop_control.escalation.terminal_reason,
        )

    def _resolve_loop_control(self, *, max_retries: int) -> LoopControl:
        process_rules: Dict[str, Any] = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules

        raw = process_rules.get("guard_loop_control")
        if isinstance(raw, dict):
            try:
                return LoopControl.model_validate(raw)
            except Exception:
                pass

        return LoopControl(
            max_retries=max(0, int(max_retries)),
            retry_backoff="none",
            escalation=LoopEscalation(
                on_exceed="halt",
                terminal_reason=TerminalReason(
                    code="GUARD_RETRY_EXCEEDED",
                    message="Guard retries exceeded configured limit.",
                ),
            ),
        )
