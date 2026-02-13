from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class GuardReviewPayload(BaseModel):
    rationale: str = ""
    violations: List[str] = Field(default_factory=list)
    remediation_actions: List[str] = Field(default_factory=list)
