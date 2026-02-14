from __future__ import annotations

from typing import Literal, List

from pydantic import BaseModel, Field, model_validator


GuardResult = Literal["pass", "fail"]
GuardSeverity = Literal["soft", "strict"]
GuardLocation = Literal["system", "user", "context", "output"]
RetryBackoff = Literal["none", "linear", "exponential"]
EscalationPolicy = Literal["halt", "fallback_role", "fallback_prompt"]


class TerminalReason(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class GuardViolation(BaseModel):
    rule_id: str = Field(min_length=1)
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    location: GuardLocation
    severity: GuardSeverity
    evidence: str | None = None


class LoopEscalation(BaseModel):
    on_exceed: EscalationPolicy
    terminal_reason: TerminalReason


class LoopControl(BaseModel):
    max_retries: int = Field(ge=0)
    retry_backoff: RetryBackoff
    escalation: LoopEscalation


class GuardContract(BaseModel):
    result: GuardResult
    violations: List[GuardViolation] = Field(default_factory=list)
    severity: GuardSeverity = "soft"
    fix_hint: str | None = None
    terminal_failure: bool = False
    terminal_reason: TerminalReason | None = None

    def _aggregated_severity(self) -> GuardSeverity:
        if not self.violations:
            return "soft"
        return "strict" if any(v.severity == "strict" for v in self.violations) else "soft"

    @model_validator(mode="after")
    def _validate_contract(self) -> "GuardContract":
        self.severity = self._aggregated_severity()
        if self.result == "pass":
            if self.violations:
                raise ValueError("pass result cannot include violations")
            if self.terminal_failure:
                raise ValueError("pass result cannot be terminal_failure")
            if self.terminal_reason is not None:
                raise ValueError("pass result cannot include terminal_reason")
            if self.fix_hint is not None:
                raise ValueError("pass result cannot include fix_hint")
            return self

        if not self.violations:
            raise ValueError("fail result requires at least one violation")
        if self.terminal_failure and self.terminal_reason is None:
            raise ValueError("terminal_failure=true requires terminal_reason")
        if (not self.terminal_failure) and self.terminal_reason is not None:
            raise ValueError("terminal_reason requires terminal_failure=true")
        return self
