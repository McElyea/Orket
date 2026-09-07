from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

DispatchPrepareStatus = Literal["prepared", "idempotent", "conflict", "cancelled", "stale"]
InvocationStatus = Literal["returned", "blocked", "failed", "cancelled", "timed_out", "protocol_failed"]
ResultAcceptanceStatus = Literal["accepted", "idempotent", "conflict", "cancelled", "stale"]
DecisionPublicationStatus = Literal["accepted", "idempotent", "conflict", "stale"]
BrokerReservationStatus = Literal[
    "prepared",
    "idempotent",
    "conflict",
    "exhausted",
    "cancelled",
    "stale",
    "uncertain",
]


@dataclass(frozen=True, slots=True)
class GovernedAgentInvocationBinding:
    """Parent-retained authority bound to one child pipe and iteration step."""

    run_id: str
    attempt_id: str
    step_id: str
    iteration_ordinal: int
    invocation_id: str
    fencing_generation: int
    cancellation_epoch: int
    deadline_utc: str
    extension_digest: str
    policy_digest: str
    request_digest: str

    def __post_init__(self) -> None:
        for field in (
            "run_id",
            "attempt_id",
            "step_id",
            "invocation_id",
            "deadline_utc",
            "extension_digest",
            "policy_digest",
            "request_digest",
        ):
            if not str(getattr(self, field)).strip():
                raise ValueError(f"E_AGENT_INVOCATION_BINDING_REQUIRED: {field}")
        if self.iteration_ordinal < 1 or self.fencing_generation < 1 or self.cancellation_epoch < 0:
            raise ValueError("E_AGENT_INVOCATION_BINDING_IDENTITY_INVALID")


@dataclass(frozen=True, slots=True)
class GovernedAgentDispatchPreparation:
    status: DispatchPrepareStatus
    binding: GovernedAgentInvocationBinding | None
    durable_dispatch_ref: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentInvocationOutcome:
    status: InvocationStatus
    binding: GovernedAgentInvocationBinding
    result_payload: Mapping[str, Any] | None
    result_digest: str | None
    normalized_reason: str | None
    child_confirmed_stopped: bool

    def __post_init__(self) -> None:
        if self.status == "returned" and (self.result_payload is None or not self.result_digest):
            raise ValueError("E_AGENT_INVOCATION_RESULT_REQUIRED")
        if self.status != "returned" and not str(self.normalized_reason or "").strip():
            raise ValueError("E_AGENT_INVOCATION_FAILURE_REASON_REQUIRED")


@dataclass(frozen=True, slots=True)
class GovernedAgentResultAcceptance:
    status: ResultAcceptanceStatus
    durable_result_ref: str | None
    accepted_result_digest: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentDecisionPublication:
    status: DecisionPublicationStatus
    durable_decision_ref: str | None
    decision_digest: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentCancellationPublication:
    status: Literal["accepted", "idempotent", "conflict", "stale"]
    cancellation_ref: str | None
    cancellation_epoch: int | None


@dataclass(frozen=True, slots=True)
class GovernedAgentIterationSnapshot:
    binding: GovernedAgentInvocationBinding
    state: str
    request_payload: Mapping[str, Any]
    result_payload: Mapping[str, Any] | None
    result_digest: str | None
    decision_inputs: Mapping[str, Any] | None
    decision_payload: Mapping[str, Any] | None
    decision_digest: str | None
    uncertainty: bool


@dataclass(frozen=True, slots=True)
class GovernedAgentBrokerReservation:
    status: BrokerReservationStatus
    durable_call_ref: str | None
    retained_result_payload: Mapping[str, Any] | None


@dataclass(frozen=True, slots=True)
class GovernedAgentBrokerCallRecord:
    invocation_id: str
    call_id: str
    operation: Literal["model.call.v1", "memory.query.v1"]
    request_digest: str
    status: Literal["reserved", "completed", "uncertain"]
    reserved_input_tokens: int
    reserved_output_tokens: int
    charged_input_tokens: int
    charged_output_tokens: int
    result_digest: str | None
    result_payload: Mapping[str, Any] | None


class GovernedAgentIterationRepository(Protocol):
    """Atomic application-owned publication port over canonical run/attempt/step records."""

    async def prepare_dispatch(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        request_payload: Mapping[str, Any],
    ) -> GovernedAgentDispatchPreparation:
        """Persist intent iff run/attempt/step/fence/cancel state still matches."""
        ...

    async def get_dispatch_binding(
        self,
        *,
        invocation_id: str,
    ) -> GovernedAgentInvocationBinding | None: ...

    async def get_dispatch_request(
        self,
        *,
        invocation_id: str,
    ) -> Mapping[str, Any] | None: ...

    async def accept_result(
        self,
        *,
        outcome: GovernedAgentInvocationOutcome,
    ) -> GovernedAgentResultAcceptance:
        """Atomically compare binding state and persist one digest-addressed result."""
        ...

    async def record_interrupted_publication(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        normalized_reason: str,
        provider_or_effect_uncertain: bool,
    ) -> str:
        """Retain uncertainty; this operation never authorizes retry or continuation."""
        ...

    async def publish_continuation_decision(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        accepted_result_digest: str,
        decision_inputs: Mapping[str, Any],
        decision_payload: Mapping[str, Any],
    ) -> GovernedAgentDecisionPublication: ...

    async def get_iteration_snapshot(
        self,
        *,
        invocation_id: str,
    ) -> GovernedAgentIterationSnapshot | None: ...

    async def list_iteration_snapshots(
        self,
        *,
        run_id: str,
    ) -> tuple[GovernedAgentIterationSnapshot, ...]: ...

    async def cancel_invocation(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        cancellation_epoch: int,
        normalized_reason: str,
    ) -> GovernedAgentCancellationPublication: ...


class GovernedAgentBrokerCallRepository(Protocol):
    """Durable per-call reservation and receipt authority."""

    async def reserve_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        operation: Literal["model.call.v1", "memory.query.v1"],
        call_id: str,
        role: str | None,
        request_digest: str,
        reserved_input_tokens: int,
        reserved_output_tokens: int,
    ) -> GovernedAgentBrokerReservation: ...

    async def complete_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        call_id: str,
        request_digest: str,
        result_payload: Mapping[str, Any],
        result_digest: str,
        charged_input_tokens: int,
        charged_output_tokens: int,
    ) -> GovernedAgentBrokerCallRecord: ...

    async def mark_call_uncertain(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        call_id: str,
        normalized_reason: str,
    ) -> GovernedAgentBrokerCallRecord: ...

    async def list_call_records(
        self,
        *,
        invocation_id: str,
    ) -> tuple[GovernedAgentBrokerCallRecord, ...]: ...

class GovernedAgentIterationInvoker(Protocol):
    """Lower-level child adapter; it never creates or closes a parent run."""

    async def invoke_once(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        request_payload: Mapping[str, Any],
    ) -> GovernedAgentInvocationOutcome: ...

    async def cancel_and_reap(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        cancellation_payload: Mapping[str, Any],
        grace_period_seconds: float,
    ) -> bool:
        """Stop new calls, send one cancel, terminate after grace, and await the tree."""
        ...


class GovernedAgentCapabilityBroker(Protocol):
    """Host-owned capability port that revalidates the retained binding per call."""

    async def dispatch_call(
        self,
        *,
        binding: GovernedAgentInvocationBinding,
        operation: Literal["model.call.v1", "memory.query.v1"],
        call_payload: Mapping[str, Any],
    ) -> Mapping[str, Any]: ...
