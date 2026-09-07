from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Self, cast

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, PlainSerializer

from .agent_validation import validate_governed_agent_payload
from .controller import canonical_json


@dataclass(frozen=True, slots=True)
class FrozenJson:
    """Deeply immutable JSON value stored as canonical bytes-in-text form."""

    canonical: str

    @classmethod
    def freeze(cls, value: Any) -> FrozenJson:
        if isinstance(value, cls):
            return value
        return cls(canonical=canonical_json(value))

    def thaw(self) -> Any:
        return json.loads(self.canonical)


FrozenJsonValue = Annotated[
    FrozenJson,
    BeforeValidator(FrozenJson.freeze),
    PlainSerializer(lambda value: value.thaw(), return_type=Any),
]


class AgentContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class AgentWireModel(AgentContractModel):
    def to_wire(self) -> dict[str, Any]:
        payload = cast(dict[str, Any], self.model_dump(mode="json"))
        _strip_omitted_none_fields(payload)
        validate_governed_agent_payload(payload)
        return payload

    @classmethod
    def from_wire(cls, payload: dict[str, Any]) -> Self:
        validate_governed_agent_payload(payload)
        return cast(Self, cls.model_validate(payload))


_OMIT_WHEN_NONE = {
    "agent_model_profile_request": ("profile_ref", "capability_class"),
    "agent_iteration_request": ("accepted_checkpoint_ref", "recovery_ref"),
    "agent_iteration_result": ("advisory_proposal", "advisory_proposal_ref"),
    "agent_model_call_request": ("profile_ref", "capability_class", "response_schema", "temperature", "seed"),
    "agent_effect_proposal": ("arguments", "arguments_ref"),
}

_OMIT_NESTED_WHEN_NONE = frozenset({"name"})


def _strip_omitted_none_fields(value: Any) -> None:
    if isinstance(value, dict):
        for field in _OMIT_WHEN_NONE.get(str(value.get("object_type") or ""), ()):
            if value.get(field) is None:
                value.pop(field, None)
        for field in _OMIT_NESTED_WHEN_NONE:
            if value.get(field) is None:
                value.pop(field, None)
        for item in value.values():
            _strip_omitted_none_fields(item)
    elif isinstance(value, list):
        for item in value:
            _strip_omitted_none_fields(item)


class AgentIdentity(AgentContractModel):
    run_id: str = Field(min_length=1, max_length=256)
    attempt_id: str = Field(min_length=1, max_length=256)
    iteration_ordinal: int = Field(ge=1)
    step_id: str = Field(min_length=1, max_length=256)
    trace_id: str = Field(min_length=1, max_length=256)
    invocation_id: str = Field(min_length=1, max_length=256)
    fencing_generation: int = Field(ge=1)


class AgentRoleCounter(AgentContractModel):
    role: str = Field(min_length=1, max_length=64)
    count: int = Field(ge=0)


class AgentCapabilityCounter(AgentContractModel):
    capability: str = Field(min_length=1, max_length=256)
    count: int = Field(ge=0)


class AgentBudgetSnapshot(AgentContractModel):
    schema_version: Literal["agent_budget_snapshot.v1"]
    snapshot_ref: str = Field(min_length=1, max_length=1024)
    snapshot_digest: str
    scope: Literal["run_limit", "iteration_limit", "run_remaining", "iteration_remaining"]
    iterations: int = Field(ge=0)
    wall_time_ms: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    per_role_model_calls: tuple[AgentRoleCounter, ...]
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    effect_proposals: int = Field(ge=0)
    per_capability_effects: tuple[AgentCapabilityCounter, ...]
    output_bytes: int = Field(ge=0)
    artifact_bytes: int = Field(ge=0)
    repair_attempts: int = Field(ge=0)
    consecutive_failures: int = Field(ge=0)
    repeated_states: int = Field(ge=0)
    no_progress_iterations: int = Field(ge=0)
    total_inference_concurrency: int = Field(ge=0)
    per_role_inference_concurrency: tuple[AgentRoleCounter, ...]


class AgentMaterializedInput(AgentContractModel):
    reference: str = Field(min_length=1, max_length=1024)
    kind: Literal["objective", "acceptance", "authoritative_context", "prior_verified_output"]
    media_type: str = Field(min_length=1, max_length=128)
    encoding: Literal["utf8", "json", "base64"]
    digest: str
    encoded_bytes: int = Field(ge=0, le=262_144)
    content: FrozenJsonValue
    provenance_refs: tuple[str, ...]


class AgentModelProfileRequest(AgentWireModel):
    object_type: Literal["agent_model_profile_request"] = "agent_model_profile_request"
    schema_version: Literal["agent_model_profile_request.v1"] = "agent_model_profile_request.v1"
    role: str = Field(min_length=1, max_length=64)
    profile_ref: str | None = None
    capability_class: str | None = None
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    timeout_ms: int = Field(ge=1)
    response_mode: Literal["text", "json"]
    streaming_preference: Literal["disabled", "preferred", "required"]


class AgentCancellation(AgentWireModel):
    object_type: Literal["agent_cancellation"] = "agent_cancellation"
    schema_version: Literal["agent_cancellation.v1"] = "agent_cancellation.v1"
    requested: bool
    cancellation_epoch: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=1024)


class AgentModelMessage(AgentContractModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(max_length=131_072)
    name: str | None = Field(default=None, min_length=1, max_length=128)


class AgentToolDescription(AgentContractModel):
    name: str = Field(min_length=1, max_length=256)
    description: str = Field(max_length=4096)
    input_schema: FrozenJsonValue


class AgentModelUseReceipt(AgentWireModel):
    object_type: Literal["agent_model_use_receipt"] = "agent_model_use_receipt"
    schema_version: Literal["agent_model_use_receipt.v1"] = "agent_model_use_receipt.v1"
    identity: AgentIdentity
    call_id: str = Field(min_length=1, max_length=256)
    role: str = Field(min_length=1, max_length=64)
    requested_profile_ref: str = Field(min_length=1, max_length=1024)
    resolved_profile_ref: str = Field(min_length=1, max_length=1024)
    provider: str = Field(min_length=1, max_length=256)
    provider_version: str | None = Field(max_length=256)
    model: str = Field(min_length=1, max_length=1024)
    model_digest: str | None
    status: Literal["returned", "failed", "cancelled", "timed_out", "uncertain"]
    usage_posture: Literal["measured", "estimated", "unknown"]
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    estimate_source: str | None = Field(max_length=256)
    charged_input_tokens: int = Field(ge=0)
    charged_output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    finish_reason: str | None = Field(max_length=128)
    truncated: bool
    substitution_posture: Literal["requested", "substituted", "degraded"]


class AgentEffectProposal(AgentWireModel):
    object_type: Literal["agent_effect_proposal"] = "agent_effect_proposal"
    schema_version: Literal["agent_effect_proposal.v1"] = "agent_effect_proposal.v1"
    identity: AgentIdentity
    proposal_id: str = Field(min_length=1, max_length=256)
    capability: str = Field(min_length=1, max_length=256)
    intended_target: str = Field(min_length=1, max_length=1024)
    namespace: str = Field(min_length=1, max_length=1024)
    arguments: FrozenJsonValue | None = None
    arguments_ref: str | None = Field(default=None, min_length=1, max_length=1024)
    arguments_digest: str
    idempotency_key: str = Field(min_length=1, max_length=256)
    evidence_refs: tuple[str, ...]


class AgentEffectReceipt(AgentContractModel):
    receipt_id: str = Field(min_length=1, max_length=256)
    proposal_id: str = Field(min_length=1, max_length=256)
    identity: AgentIdentity
    capability: str = Field(min_length=1, max_length=256)
    intended_target: str = Field(min_length=1, max_length=1024)
    arguments_digest: str
    state: Literal["proposed", "approved", "denied", "executed", "observed", "uncertain", "reconciled"]
    authority_ref: str = Field(min_length=1, max_length=1024)
    observation_refs: tuple[str, ...]


class AgentProgress(AgentWireModel):
    object_type: Literal["agent_progress"] = "agent_progress"
    schema_version: Literal["agent_progress.v1"] = "agent_progress.v1"
    identity: AgentIdentity
    sequence: int = Field(ge=1)
    summary: str = Field(min_length=1, max_length=8192)
    evidence_refs: tuple[str, ...]


class AgentUsage(AgentWireModel):
    object_type: Literal["agent_usage"] = "agent_usage"
    schema_version: Literal["agent_usage.v1"] = "agent_usage.v1"
    model_calls: int = Field(ge=0)
    usage_posture: Literal["measured", "estimated", "unknown"]
    input_tokens: int | None = Field(ge=0)
    output_tokens: int | None = Field(ge=0)
    estimate_source: str | None = Field(max_length=256)
    charged_input_tokens: int = Field(ge=0)
    charged_output_tokens: int = Field(ge=0)
    effect_proposals: int = Field(ge=0)
    output_bytes: int = Field(ge=0)
    artifact_bytes: int = Field(ge=0)
    repair_attempts: int = Field(ge=0)


class AgentHandoffProposal(AgentContractModel):
    identity: AgentIdentity
    handoff_id: str = Field(min_length=1, max_length=256)
    source_role: str = Field(min_length=1, max_length=64)
    target_role: str = Field(min_length=1, max_length=64)
    target_profile_ref: str = Field(min_length=1, max_length=1024)
    scope: str = Field(min_length=1, max_length=1024)
    artifact_refs: tuple[str, ...]
    provenance_refs: tuple[str, ...]
    requested_capabilities: tuple[str, ...]
    requested_model_calls: int = Field(ge=0)
    requested_input_tokens: int = Field(ge=0)
    requested_output_tokens: int = Field(ge=0)


class AgentMemoryWriteProposal(AgentContractModel):
    identity: AgentIdentity
    proposal_id: str = Field(min_length=1, max_length=256)
    scope: Literal["extension_private", "role_private", "team_shared", "objective"]
    role: str | None = Field(default=None, max_length=64)
    content: FrozenJsonValue
    content_digest: str
    provenance_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
