from __future__ import annotations

import enum
import json
from pathlib import Path
from typing import Any, Dict, List, Literal

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GuardName(str, enum.Enum):
    HALLUCINATION = "hallucination"
    STRUCTURE = "structure"
    SAFETY = "safety"
    SECURITY = "security"
    CONSISTENCY = "consistency"


class OrketMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    displayName: str | None = None
    description: str | None = None
    version: str = Field(min_length=1)
    engineVersion: str = Field(min_length=1)

    @field_validator("version")
    @classmethod
    def _validate_semver(cls, value: str) -> str:
        text = str(value or "").strip()
        try:
            Version(text)
        except InvalidVersion as exc:
            raise ValueError(f"metadata.version is not a valid version: {value}") from exc
        return text

    @field_validator("engineVersion")
    @classmethod
    def _validate_engine_version_specifier(cls, value: str) -> str:
        text = str(value or "").strip()
        try:
            SpecifierSet(text)
        except InvalidSpecifier as exc:
            raise ValueError(
                f"metadata.engineVersion is not parseable as a version specifier: {value}"
            ) from exc
        return text


class ModelPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    preferred: str = Field(min_length=1)
    minimum: str = Field(min_length=1)
    fallback: List[str] = Field(default_factory=list)
    allowOverride: bool = True

    @field_validator("fallback")
    @classmethod
    def _validate_fallback_entries(cls, value: List[str]) -> List[str]:
        normalized = [str(item).strip() for item in value if str(item).strip()]
        if len(set(normalized)) != len(normalized):
            raise ValueError("model.fallback contains duplicates")
        return normalized


class AgentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    role: str = Field(min_length=1)


class StateMachineRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file: str = Field(min_length=1)


class PersistenceSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    storageDir: str = Field(min_length=1)
    retainHistory: bool = True


class FilesystemPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read: List[str] = Field(default_factory=list)
    write: List[str] = Field(default_factory=list)


class NetworkPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: bool


class ToolPermissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed: List[str] = Field(default_factory=list)


class PermissionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filesystem: FilesystemPermissions
    network: NetworkPermissions
    tools: ToolPermissions


class OrketManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    apiVersion: Literal["orket.io/v1"]
    kind: Literal["Orket"]
    metadata: OrketMetadata
    model: ModelPolicy
    agents: List[AgentSpec] = Field(min_length=1)
    guards: List[GuardName] = Field(min_length=1)
    stateMachine: StateMachineRef
    persistence: PersistenceSettings
    permissions: PermissionPolicy

    @field_validator("guards")
    @classmethod
    def _guards_must_be_unique(cls, value: List[GuardName]) -> List[GuardName]:
        raw = [item.value for item in value]
        if len(set(raw)) != len(raw):
            raise ValueError("guards contains duplicates")
        return value


def load_orket_manifest(path: str | Path) -> OrketManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("manifest payload must be a JSON object")
    return OrketManifest.model_validate(raw)


def manifest_json_schema() -> Dict[str, Any]:
    return OrketManifest.model_json_schema()


def is_engine_compatible(manifest: OrketManifest, engine_version: str) -> bool:
    spec = SpecifierSet(str(manifest.metadata.engineVersion or "").strip())
    version = Version(str(engine_version or "").strip())
    return version in spec


def resolve_model_selection(
    manifest: OrketManifest,
    *,
    available_models: List[str],
    model_override: str = "",
) -> Dict[str, Any]:
    available = [str(item).strip() for item in available_models if str(item).strip()]
    available_set = set(available)
    override = str(model_override or "").strip()

    if override:
        if not bool(manifest.model.allowOverride):
            return {
                "ok": False,
                "code": "E_MODEL_OVERRIDE_NOT_ALLOWED",
                "message": "Model override is not allowed by manifest policy.",
                "selected_model": None,
            }
        if override not in available_set:
            return {
                "ok": False,
                "code": "E_MODEL_OVERRIDE_UNAVAILABLE",
                "message": f"Requested override model is unavailable: {override}",
                "selected_model": None,
            }
        return {
            "ok": True,
            "code": None,
            "message": None,
            "selected_model": override,
            "selection_source": "override",
        }

    candidates: List[str] = []
    for item in [manifest.model.preferred, manifest.model.minimum, *manifest.model.fallback]:
        normalized = str(item).strip()
        if not normalized or normalized in candidates:
            continue
        candidates.append(normalized)

    for candidate in candidates:
        if candidate in available_set:
            return {
                "ok": True,
                "code": None,
                "message": None,
                "selected_model": candidate,
                "selection_source": "manifest_policy",
            }
    return {
        "ok": False,
        "code": "E_MODEL_CANDIDATE_UNAVAILABLE",
        "message": (
            "No compatible model candidate is available. "
            f"Candidates={candidates}, available={available}"
        ),
        "selected_model": None,
    }
