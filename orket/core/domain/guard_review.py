from __future__ import annotations

from pydantic import BaseModel, Field


class GuardReviewPayload(BaseModel):
    rationale: str = ""
    violations: list[str] = Field(default_factory=list)
    remediation_actions: list[str] = Field(default_factory=list)
