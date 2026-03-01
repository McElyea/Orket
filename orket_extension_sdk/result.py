from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


IssueSeverity = Literal["error", "warning", "info"]


class Issue(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    severity: IssueSeverity = "error"
    path: str | None = None


class ArtifactRef(BaseModel):
    path: str = Field(min_length=1)
    digest_sha256: str = Field(min_length=1)
    kind: str | None = None


class WorkloadResult(BaseModel):
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
