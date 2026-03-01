from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
from typing import Any, Dict, Literal
from pydantic import ValidationError

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
    retry_fingerprint: str | None = None
    repeated_fingerprint: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "next_retry_count": self.next_retry_count,
            "terminal_failure": self.terminal_failure,
            "retry_fingerprint": self.retry_fingerprint,
            "repeated_fingerprint": self.repeated_fingerprint,
            "terminal_reason": (
                None if self.terminal_reason is None else self.terminal_reason.model_dump()
            ),
        }


class GuardEvaluator:
    """
    Guard check evaluator boundary.

    This class owns check evaluation output and emits GuardContract.
    Current baseline accepts an already-built GuardContract from upstream guards.
    """

    def evaluate_contract(self, *, contract: GuardContract) -> GuardContract:
        return contract


class GuardController:
    """
    Guard loop controller boundary.

    Interprets GuardContract with loop policy and decides pass/retry/terminal_failure.
    """

    def __init__(self, organization: Any = None):
        self.organization = organization

    def decide(
        self,
        *,
        contract: GuardContract,
        retry_count: int,
        max_retries: int,
        output_text: str | None = None,
        seen_fingerprints: list[str] | None = None,
    ) -> GuardDecision:
        if contract.result == "pass":
            return GuardDecision(
                action="pass",
                next_retry_count=retry_count,
                terminal_failure=False,
                terminal_reason=None,
            )

        fingerprint = self._build_retry_fingerprint(contract=contract, output_text=output_text)
        if fingerprint and isinstance(seen_fingerprints, list):
            if fingerprint in seen_fingerprints:
                return GuardDecision(
                    action="terminal_failure",
                    next_retry_count=int(retry_count),
                    terminal_failure=True,
                    terminal_reason=TerminalReason(
                        code="MODEL_NON_COMPLIANT",
                        message="Repeated identical guard failure fingerprint.",
                    ),
                    retry_fingerprint=fingerprint,
                    repeated_fingerprint=True,
                )
            seen_fingerprints.append(fingerprint)

        if contract.terminal_failure:
            return GuardDecision(
                action="terminal_failure",
                next_retry_count=retry_count,
                terminal_failure=True,
                terminal_reason=contract.terminal_reason,
                retry_fingerprint=fingerprint,
                repeated_fingerprint=False,
            )

        loop_control = self._resolve_loop_control(max_retries=max_retries)
        allowed_retries = max(0, min(int(max_retries), int(loop_control.max_retries)))
        if int(retry_count) < allowed_retries:
            return GuardDecision(
                action="retry",
                next_retry_count=int(retry_count) + 1,
                terminal_failure=False,
                terminal_reason=None,
                retry_fingerprint=fingerprint,
                repeated_fingerprint=False,
            )

        terminal_reason = loop_control.escalation.terminal_reason
        if self._is_hallucination_contract(contract):
            terminal_reason = TerminalReason(
                code="HALLUCINATION_PERSISTENT",
                message="The model repeatedly invented or referenced out-of-scope details.",
            )
        return GuardDecision(
            action="terminal_failure",
            next_retry_count=int(retry_count),
            terminal_failure=True,
            terminal_reason=terminal_reason,
            retry_fingerprint=fingerprint,
            repeated_fingerprint=False,
        )

    def _resolve_loop_control(self, *, max_retries: int) -> LoopControl:
        process_rules: Dict[str, Any] = {}
        if self.organization and isinstance(getattr(self.organization, "process_rules", None), dict):
            process_rules = self.organization.process_rules

        raw = process_rules.get("guard_loop_control")
        if isinstance(raw, dict):
            try:
                return LoopControl.model_validate(raw)
            except ValidationError:
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

    @staticmethod
    def _is_hallucination_contract(contract: GuardContract) -> bool:
        for violation in contract.violations:
            rule_id = str(getattr(violation, "rule_id", "") or "").strip().upper()
            code = str(getattr(violation, "code", "") or "").strip().upper()
            if rule_id.startswith("HALLUCINATION.") or code.startswith("HALLUCINATION_"):
                return True
        return False

    @staticmethod
    def _build_retry_fingerprint(*, contract: GuardContract, output_text: str | None) -> str:
        violation_codes = sorted(
            {
                str(getattr(violation, "code", "") or "").strip().upper()
                for violation in contract.violations
                if str(getattr(violation, "code", "") or "").strip()
            }
        )
        normalized = GuardController._normalize_output_for_fingerprint(output_text or "")
        payload = "|".join(violation_codes) + "::" + normalized
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _normalize_output_for_fingerprint(content: str) -> str:
        if not content:
            return ""
        normalized = re.sub(r"\s+", " ", str(content)).strip().lower()
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}t\d{2}:\d{2}:\d{2}(?:\.\d+)?z", "<timestamp>", normalized)
        return normalized[:2000]


class GuardAgent:
    """
    Non-generative guard evaluator.

    Evaluates GuardContract outcomes and returns deterministic loop decisions
    (pass/retry/terminal_failure) based on bounded retry policy.
    """

    def __init__(self, organization: Any = None):
        self.organization = organization
        self.evaluator = GuardEvaluator()
        self.controller = GuardController(organization)

    def evaluate(
        self,
        *,
        contract: GuardContract,
        retry_count: int,
        max_retries: int,
        output_text: str | None = None,
        seen_fingerprints: list[str] | None = None,
    ) -> GuardDecision:
        evaluated_contract = self.evaluator.evaluate_contract(contract=contract)
        return self.controller.decide(
            contract=evaluated_contract,
            retry_count=retry_count,
            max_retries=max_retries,
            output_text=output_text,
            seen_fingerprints=seen_fingerprints,
        )
