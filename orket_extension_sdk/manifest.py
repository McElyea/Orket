from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

SUPPORTED_MANIFEST_VERSION = "v0"
GOVERNED_AGENT_CONTRACT_VERSION = "governed_agent_loop.v1"
AGENT_ITERATION_INPUT_CONTRACT = "agent_iteration_request.v1"
AGENT_ITERATION_OUTPUT_CONTRACT = "agent_iteration_result.v1"
AGENT_ITERATION_CAPABILITY = "agent.iteration.v1"
AGENT_STDIO_IPC_FEATURE = "agent_stdio_ipc.v1"
AGENT_MODEL_RECEIPT_FEATURE = "agent_model_use_receipt.v2"
GOVERNED_AGENT_REQUIRED_HOST_FEATURES = frozenset(
    {GOVERNED_AGENT_CONTRACT_VERSION, AGENT_STDIO_IPC_FEATURE, AGENT_MODEL_RECEIPT_FEATURE}
)
GOVERNED_AGENT_WORKLOAD_ID = "governed-agent-loop"
_ALTERNATE_AGENT_MARKER_FIELDS = frozenset(
    {
        "agent_contract",
        "agent_contract_version",
        "agent_input_contract",
        "agent_output_contract",
        "required_host_features",
    }
)


def agent_discriminator_reasons(payload: Mapping[str, Any]) -> tuple[str, ...]:
    """Return every field that makes a raw manifest row agent-like.

    This operates on the raw row so permissive manifest-v0 parsing cannot erase
    a marker before admission decides whether the row needs strict validation.
    """
    reasons: list[str] = []
    if str(payload.get("workload_id") or "").strip() == GOVERNED_AGENT_WORKLOAD_ID:
        reasons.append("workload_id")
    if str(payload.get("workload_kind") or "").strip() == "agent":
        reasons.append("workload_kind")
    if payload.get("agent") is not None:
        reasons.append("agent")
    capabilities = payload.get("required_capabilities")
    if isinstance(capabilities, list) and AGENT_ITERATION_CAPABILITY in {
        str(item or "").strip() for item in capabilities
    }:
        reasons.append("required_capabilities")
    if str(payload.get("input_contract") or "").strip() == AGENT_ITERATION_INPUT_CONTRACT:
        reasons.append("input_contract")
    if str(payload.get("output_contract") or "").strip() == AGENT_ITERATION_OUTPUT_CONTRACT:
        reasons.append("output_contract")
    reasons.extend(sorted(_ALTERNATE_AGENT_MARKER_FIELDS.intersection(payload)))
    return tuple(reasons)


def is_agent_workload_payload(payload: Mapping[str, Any]) -> bool:
    return bool(agent_discriminator_reasons(payload))


def unsupported_agent_host_features(
    workload: WorkloadManifest,
    *,
    supported_features: Iterable[str],
) -> tuple[str, ...]:
    if workload.agent is None:
        return ()
    supported = {str(item or "").strip() for item in supported_features}
    return tuple(sorted(set(workload.agent.required_host_features) - supported))


class AgentModelProfileDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: str = Field(min_length=1, max_length=64)
    profile_ref: str = Field(min_length=1, max_length=256)


class AgentResourceRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    max_model_calls_per_iteration: int = Field(ge=1, le=32)
    max_progress_events_per_iteration: int = Field(default=32, ge=0, le=256)
    max_result_bytes: int = Field(default=262_144, ge=1_024, le=1_048_576)
    max_inference_concurrency: Literal[1] = 1


class AgentWorkloadDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["governed_agent_loop.v1"]
    required_host_features: list[str] = Field(min_length=1)
    model_profiles: list[AgentModelProfileDeclaration] = Field(min_length=1, max_length=16)
    recovery_posture: Literal["fail_closed", "operator_required"] = "fail_closed"
    resource_requirements: AgentResourceRequirements

    @model_validator(mode="after")
    def require_v1_host_features(self) -> AgentWorkloadDeclaration:
        if len(set(self.required_host_features)) != len(self.required_host_features):
            raise ValueError("E_SDK_AGENT_HOST_FEATURE_DUPLICATE")
        missing = sorted(GOVERNED_AGENT_REQUIRED_HOST_FEATURES - set(self.required_host_features))
        if missing:
            raise ValueError("E_SDK_AGENT_HOST_FEATURE_REQUIRED: " + ", ".join(missing))
        roles = [profile.role for profile in self.model_profiles]
        if len(set(roles)) != len(roles):
            raise ValueError("E_SDK_AGENT_ROLE_DUPLICATE")
        return self


class WorkloadManifest(BaseModel):
    workload_id: str = Field(min_length=1)
    entrypoint: str = Field(min_length=1)
    required_capabilities: list[str] = Field(default_factory=list)
    workload_kind: Literal["generic", "agent"] = "generic"
    input_contract: str | None = None
    output_contract: str | None = None
    agent: AgentWorkloadDeclaration | None = None

    @model_validator(mode="before")
    @classmethod
    def require_coherent_agent_discriminators(cls, value: Any) -> Any:
        if not isinstance(value, Mapping):
            return value
        reasons = agent_discriminator_reasons(value)
        alternate = sorted(_ALTERNATE_AGENT_MARKER_FIELDS.intersection(value))
        if alternate:
            raise ValueError("E_SDK_AGENT_MARKER_UNRECOGNIZED: " + ", ".join(alternate))
        if reasons and str(value.get("workload_kind") or "").strip() != "agent":
            raise ValueError("E_SDK_AGENT_KIND_REQUIRED: " + ", ".join(reasons))
        return value

    @model_validator(mode="after")
    def validate_agent_contract(self) -> WorkloadManifest:
        if self.workload_kind != "agent":
            if self.agent is not None:
                raise ValueError("E_SDK_AGENT_KIND_REQUIRED")
            return self
        if self.agent is None:
            raise ValueError("E_SDK_AGENT_DECLARATION_REQUIRED")
        if AGENT_ITERATION_CAPABILITY not in self.required_capabilities:
            raise ValueError(f"E_SDK_AGENT_CAPABILITY_REQUIRED: {AGENT_ITERATION_CAPABILITY}")
        if len(set(self.required_capabilities)) != len(self.required_capabilities):
            raise ValueError("E_SDK_AGENT_CAPABILITY_DUPLICATE")
        if self.input_contract != AGENT_ITERATION_INPUT_CONTRACT:
            raise ValueError(f"E_SDK_AGENT_INPUT_CONTRACT_UNSUPPORTED: {self.input_contract}")
        if self.output_contract != AGENT_ITERATION_OUTPUT_CONTRACT:
            raise ValueError(f"E_SDK_AGENT_OUTPUT_CONTRACT_UNSUPPORTED: {self.output_contract}")
        return self


def validate_workload_manifest_payload(payload: Mapping[str, Any]) -> WorkloadManifest:
    """Strictly validate agent-like rows while preserving generic v0 extras."""
    try:
        return WorkloadManifest.model_validate(dict(payload))
    except ValidationError as exc:
        raise ValueError(f"E_SDK_AGENT_DECLARATION_INVALID: {exc}") from exc


class ExtensionManifest(BaseModel):
    manifest_version: str = Field(min_length=1)
    extension_id: str = Field(min_length=1)
    extension_version: str = Field(min_length=1)
    config_sections: list[str] = Field(default_factory=list)
    allowed_stdlib_modules: list[str] = Field(default_factory=list)
    workloads: list[WorkloadManifest] = Field(default_factory=list)


def load_manifest(path: Path) -> ExtensionManifest:
    payload = _load_payload(path)
    try:
        manifest = ExtensionManifest.model_validate(payload)
    except ValidationError as exc:  # pragma: no cover - exercised by tests
        raise ValueError(f"E_SDK_MANIFEST_SCHEMA: {exc}") from exc
    if manifest.manifest_version != SUPPORTED_MANIFEST_VERSION:
        raise ValueError(
            "E_SDK_MANIFEST_VERSION_UNSUPPORTED: "
            f"manifest_version must be '{SUPPORTED_MANIFEST_VERSION}'"
        )
    return manifest


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"E_SDK_MANIFEST_NOT_FOUND: {path}")
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    try:
        if suffix == ".json":
            payload = json.loads(text)
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml
            except ModuleNotFoundError as exc:
                raise ValueError("E_SDK_MANIFEST_PARSE: PyYAML not available") from exc
            payload = yaml.safe_load(text)
        else:
            raise ValueError(f"E_SDK_MANIFEST_PARSE: unsupported extension '{suffix}'")
    except (json.JSONDecodeError, ValueError) as exc:
        if str(exc).startswith("E_SDK_"):
            raise
        raise ValueError(f"E_SDK_MANIFEST_PARSE: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("E_SDK_MANIFEST_SCHEMA: root must be object")
    return payload
