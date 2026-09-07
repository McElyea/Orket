from __future__ import annotations

from typing import Literal

from pydantic import Field

from .agent_types import (
    AgentBudgetSnapshot,
    AgentCancellation,
    AgentContractModel,
    AgentEffectProposal,
    AgentEffectReceipt,
    AgentHandoffProposal,
    AgentIdentity,
    AgentMaterializedInput,
    AgentMemoryWriteProposal,
    AgentModelMessage,
    AgentModelProfileRequest,
    AgentModelUseReceipt,
    AgentProgress,
    AgentToolDescription,
    AgentUsage,
    AgentWireModel,
    FrozenJsonValue,
)


class GovernedAgentSubmission(AgentWireModel):
    object_type: Literal["governed_agent_submission"] = "governed_agent_submission"
    schema_version: Literal["governed_agent_submission.v1"] = "governed_agent_submission.v1"
    objective_ref: str = Field(min_length=1, max_length=1024)
    acceptance_ref: str = Field(min_length=1, max_length=1024)
    initial_context_refs: tuple[str, ...]
    extension_id: str = Field(min_length=1, max_length=256)
    workload_id: Literal["governed-agent-loop"] = "governed-agent-loop"
    agent_contract_version: Literal["governed_agent_loop.v1"] = "governed_agent_loop.v1"
    allowed_capabilities: tuple[str, ...]
    namespace_scope: tuple[str, ...]
    policy_ref: str = Field(min_length=1, max_length=1024)
    policy_digest: str
    policy_schema_version: str = Field(min_length=1, max_length=256)
    run_budget: AgentBudgetSnapshot
    iteration_budget: AgentBudgetSnapshot
    verifier_class: str = Field(min_length=1, max_length=256)
    verifier_config: FrozenJsonValue
    requested_model_profiles: tuple[AgentModelProfileRequest, ...]
    recovery_posture: Literal["fail_closed", "operator_required"]
    operator_ref: str = Field(min_length=1, max_length=1024)


class AgentIterationRequest(AgentWireModel):
    object_type: Literal["agent_iteration_request"] = "agent_iteration_request"
    schema_version: Literal["agent_iteration_request.v1"] = "agent_iteration_request.v1"
    identity: AgentIdentity
    objective_ref: str = Field(min_length=1, max_length=1024)
    acceptance_ref: str = Field(min_length=1, max_length=1024)
    authoritative_context_refs: tuple[str, ...]
    prior_verified_output_refs: tuple[str, ...]
    materialized_inputs: tuple[AgentMaterializedInput, ...]
    effect_receipts: tuple[AgentEffectReceipt, ...]
    admitted_capabilities: tuple[str, ...]
    namespace_scope: tuple[str, ...]
    model_profiles: tuple[AgentModelProfileRequest, ...]
    policy_ref: str = Field(min_length=1, max_length=1024)
    policy_digest: str
    remaining_run_budget: AgentBudgetSnapshot
    remaining_iteration_budget: AgentBudgetSnapshot
    deadline_utc: str
    lease_expires_at_utc: str
    accepted_checkpoint_ref: str | None = Field(default=None, max_length=1024)
    recovery_ref: str | None = Field(default=None, max_length=1024)
    cancellation: AgentCancellation
    extension_config: FrozenJsonValue


class AgentIterationResult(AgentWireModel):
    object_type: Literal["agent_iteration_result"] = "agent_iteration_result"
    schema_version: Literal["agent_iteration_result.v1"] = "agent_iteration_result.v1"
    identity: AgentIdentity
    invocation_status: Literal["returned", "blocked", "failed", "cancelled"]
    observations: tuple[str, ...]
    advisory_proposal: str | None = Field(default=None, max_length=65_536)
    advisory_proposal_ref: str | None = Field(default=None, max_length=1024)
    effect_proposals: tuple[AgentEffectProposal, ...]
    progress_claims: tuple[AgentProgress, ...]
    completion_recommendation: Literal["continue", "pause", "stop", "complete"]
    completion_evidence_refs: tuple[str, ...]
    handoff_proposals: tuple[AgentHandoffProposal, ...]
    memory_write_proposals: tuple[AgentMemoryWriteProposal, ...]
    model_receipts: tuple[AgentModelUseReceipt, ...]
    usage: AgentUsage
    normalized_reason: str | None = Field(max_length=2048)


class AgentModelCallRequest(AgentWireModel):
    object_type: Literal["agent_model_call_request"] = "agent_model_call_request"
    schema_version: Literal["agent_model_call_request.v1"] = "agent_model_call_request.v1"
    identity: AgentIdentity
    call_id: str = Field(min_length=1, max_length=256)
    role: str = Field(min_length=1, max_length=64)
    profile_ref: str | None = Field(default=None, max_length=1024)
    capability_class: str | None = Field(default=None, max_length=128)
    messages: tuple[AgentModelMessage, ...]
    response_mode: Literal["text", "json"]
    response_schema: FrozenJsonValue | None = None
    max_input_tokens: int = Field(ge=1)
    max_output_tokens: int = Field(ge=1)
    timeout_ms: int = Field(ge=1)
    temperature: float | None = Field(default=None, ge=0, le=2)
    seed: int | None = None
    streaming_preference: Literal["disabled", "preferred", "required"]
    tool_descriptions: tuple[AgentToolDescription, ...]
    stop_sequences: tuple[str, ...]


class AgentModelCallResult(AgentWireModel):
    object_type: Literal["agent_model_call_result"] = "agent_model_call_result"
    schema_version: Literal["agent_model_call_result.v1"] = "agent_model_call_result.v1"
    identity: AgentIdentity
    call_id: str = Field(min_length=1, max_length=256)
    role: str = Field(min_length=1, max_length=64)
    response: FrozenJsonValue
    response_digest: str | None
    receipt: AgentModelUseReceipt
    normalized_reason: str | None = Field(default=None, max_length=2048)


class AgentMemoryQueryRequest(AgentWireModel):
    object_type: Literal["agent_memory_query_request"] = "agent_memory_query_request"
    schema_version: Literal["agent_memory_query_request.v1"] = "agent_memory_query_request.v1"
    identity: AgentIdentity
    call_id: str = Field(min_length=1, max_length=256)
    scope: Literal["extension_private", "role_private", "team_shared", "objective"]
    role: str | None = Field(max_length=64)
    query: str = Field(min_length=1, max_length=8192)
    max_items: int = Field(ge=1, le=128)
    max_content_bytes: int = Field(ge=1, le=262_144)


class AgentMemoryEntry(AgentContractModel):
    reference: str = Field(min_length=1, max_length=1024)
    content: FrozenJsonValue
    content_digest: str
    provenance_refs: tuple[str, ...]


class AgentMemoryQueryResult(AgentWireModel):
    object_type: Literal["agent_memory_query_result"] = "agent_memory_query_result"
    schema_version: Literal["agent_memory_query_result.v1"] = "agent_memory_query_result.v1"
    identity: AgentIdentity
    call_id: str = Field(min_length=1, max_length=256)
    status: Literal["returned", "blocked", "failed", "cancelled"]
    entries: tuple[AgentMemoryEntry, ...]
    normalized_reason: str | None = Field(max_length=2048)


class AgentStdioFrame(AgentWireModel):
    object_type: Literal["agent_stdio_frame"] = "agent_stdio_frame"
    schema_version: Literal["agent_stdio_frame.v1"] = "agent_stdio_frame.v1"
    protocol_version: Literal["agent_stdio_ipc.v1"] = "agent_stdio_ipc.v1"
    invocation_id: str = Field(min_length=1, max_length=256)
    sequence: int = Field(ge=1)
    direction: Literal["parent_to_child", "child_to_parent"]
    message_type: Literal[
        "bootstrap", "ready", "capability_call", "capability_result", "progress", "iteration_result", "cancel"
    ]
    call_id: str | None = Field(max_length=256)
    operation: Literal["model.call.v1", "memory.query.v1"] | None
    payload: FrozenJsonValue
