from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SkillEntrypointContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entrypoint_id: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    command: str = Field(min_length=1)
    working_directory: str = Field(min_length=1)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    error_schema: dict[str, Any] = Field(default_factory=dict)
    args_fingerprint_fields: list[str] = Field(default_factory=list)
    result_fingerprint_fields: list[str] = Field(default_factory=list)
    side_effect_fingerprint_fields: list[str] = Field(default_factory=list)
    requested_permissions: dict[str, Any] = Field(default_factory=dict)
    required_permissions: dict[str, Any] = Field(default_factory=dict)
    tool_profile_id: str = Field(min_length=1)
    tool_profile_version: str = Field(min_length=1)


class SkillManifestContract(BaseModel):
    model_config = ConfigDict(extra="ignore")

    skill_contract_version: str = Field(min_length=1)
    skill_id: str = Field(min_length=1)
    skill_version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    manifest_digest: str = Field(min_length=1)
    entrypoints: list[SkillEntrypointContract] = Field(min_length=1)

