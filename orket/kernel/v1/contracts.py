from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


Outcome = Literal["PASS", "FAIL"]


@dataclass(frozen=True)
class KernelIssue:
    stage: str
    code: str
    location: str  # RFC6901 pointer
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    level: Literal["FAIL", "INFO"] = "FAIL"
    contract_version: str = "kernel_api/v1"


@dataclass(frozen=True)
class KernelResult:
    outcome: Outcome
    issues: list[KernelIssue] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    @staticmethod
    def pass_(events: list[str] | None = None) -> "KernelResult":
        return KernelResult(outcome="PASS", issues=[], events=events or [])

    @staticmethod
    def fail(issues: list[KernelIssue], events: list[str] | None = None) -> "KernelResult":
        return KernelResult(outcome="FAIL", issues=issues, events=events or [])
