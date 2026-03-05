from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ExecutionEnvelope(BaseModel):
    """Execution determinism envelope required by Marshaller v0 runs."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["lockfile", "container"]
    lockfile_digest: str | None = None
    container_image_digest: str | None = None
    interpreter_fingerprint: str | None = None
    os_fingerprint: str | None = None
    tool_versions: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_mode_requirements(self) -> ExecutionEnvelope:
        if self.mode == "lockfile" and not (self.lockfile_digest or "").strip():
            raise ValueError("lockfile_digest is required when mode='lockfile'")
        if self.mode == "container" and not (self.container_image_digest or "").strip():
            raise ValueError("container_image_digest is required when mode='container'")
        return self


class PatchProposal(BaseModel):
    """Minimum proposal contract for v0 intake validation."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str = Field(min_length=1)
    proposal_contract_version: str = Field(min_length=1)
    base_revision_digest: str = Field(min_length=1)
    patch: str = Field(min_length=1)
    intent: str = Field(min_length=1)
    touched_paths: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)

    @field_validator("touched_paths")
    @classmethod
    def _validate_touched_paths(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise ValueError("touched_paths must contain at least one non-empty path")
        return cleaned


class RunRequest(BaseModel):
    """Run intake contract for Marshaller v0."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str = Field(min_length=1)
    task_spec: dict[str, Any]
    checks: list[str] = Field(min_length=1)
    seed: int
    max_attempts: int = Field(ge=1)
    execution_envelope: ExecutionEnvelope
    model_streams: int = Field(default=1, ge=1)

    @field_validator("checks")
    @classmethod
    def _validate_checks(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if not cleaned:
            raise ValueError("checks must contain at least one check id")
        return cleaned
