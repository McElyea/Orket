from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal, Protocol

WakeSource = Literal["manual", "api", "scheduled", "webhook", "recovery"]
WakeTargetKind = Literal["existing_run", "new_run"]
WakeState = Literal["queued", "claimed", "completed", "cancelled", "recovery_required"]
WakeEnqueueStatus = Literal["enqueued", "idempotent", "conflict"]
WakeClaimStatus = Literal["claimed", "idempotent", "empty", "capacity"]
WakeTransitionStatus = Literal["applied", "idempotent", "stale", "conflict"]
WakeControlKind = Literal["cancel", "recover"]
WakeRecoveryResolution = Literal["requeue", "confirm_cancelled"]


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeRequest:
    wake_id: str
    source: WakeSource
    target_kind: WakeTargetKind
    target_run_id: str | None
    workload_id: str | None
    occurrence_id: str
    deduplication_key: str
    payload: Mapping[str, Any]
    created_at_utc: str


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeRecord:
    wake_id: str
    source: WakeSource
    target_kind: WakeTargetKind
    target_run_id: str | None
    workload_id: str | None
    occurrence_id: str
    deduplication_key: str
    payload: Mapping[str, Any]
    payload_digest: str
    created_at_utc: str
    state: WakeState
    claim_owner_id: str | None
    lease_expires_at_utc: str | None
    fencing_generation: int
    cancellation_epoch: int
    uncertainty: bool
    result_ref: str | None
    last_reason: str | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeAuthority:
    wake_id: str
    owner_id: str
    fencing_generation: int
    cancellation_epoch: int
    lease_expires_at_utc: str


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeEnqueueResult:
    status: WakeEnqueueStatus
    wake: GovernedAgentWakeRecord | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeClaimResult:
    status: WakeClaimStatus
    wake: GovernedAgentWakeRecord | None
    authority: GovernedAgentWakeAuthority | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeTransitionResult:
    status: WakeTransitionStatus
    wake: GovernedAgentWakeRecord | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeCancellationRequest:
    action_id: str
    wake_id: str
    actor_ref: str
    timestamp_utc: str
    reason: str
    expected_cancellation_epoch: int
    cancellation_epoch: int


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeRecoveryRequest:
    action_id: str
    wake_id: str
    actor_ref: str
    timestamp_utc: str
    reason: str
    expected_fencing_generation: int
    resolution: WakeRecoveryResolution
    child_confirmed_stopped: bool
    effect_uncertainty_cleared: bool
    evidence_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeActionRecord:
    action_id: str
    wake_id: str
    action_kind: WakeControlKind
    actor_ref: str
    timestamp_utc: str
    request: Mapping[str, Any]
    request_digest: str
    status: WakeTransitionStatus
    resulting_state: WakeState | None
    resulting_fencing_generation: int | None
    resulting_cancellation_epoch: int | None
    resulting_uncertainty: bool | None


@dataclass(frozen=True, slots=True)
class GovernedAgentWakeControlResult:
    status: WakeTransitionStatus
    wake: GovernedAgentWakeRecord | None
    action: GovernedAgentWakeActionRecord


class GovernedAgentWakeRepository(Protocol):
    async def enqueue(self, request: GovernedAgentWakeRequest) -> GovernedAgentWakeEnqueueResult: ...

    async def claim_next(
        self,
        *,
        owner_id: str,
        now_utc: str,
        lease_expires_at_utc: str,
        max_active_claims: int,
    ) -> GovernedAgentWakeClaimResult: ...

    async def validate_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
    ) -> bool: ...

    async def renew_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        lease_expires_at_utc: str,
    ) -> GovernedAgentWakeTransitionResult: ...

    async def complete_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        result_ref: str,
    ) -> GovernedAgentWakeTransitionResult: ...

    async def release_claim(
        self,
        *,
        authority: GovernedAgentWakeAuthority,
        now_utc: str,
        reason: str,
        child_confirmed_stopped: bool,
        effect_uncertainty: bool,
    ) -> GovernedAgentWakeTransitionResult: ...

    async def cancel_wake(
        self,
        *,
        wake_id: str,
        expected_cancellation_epoch: int,
        cancellation_epoch: int,
        reason: str,
    ) -> GovernedAgentWakeTransitionResult: ...

    async def recover_expired_claim(
        self,
        *,
        wake_id: str,
        expected_fencing_generation: int,
        child_confirmed_stopped: bool,
        effect_uncertainty_cleared: bool,
        reason: str,
    ) -> GovernedAgentWakeTransitionResult: ...

    async def get_wake(self, *, wake_id: str) -> GovernedAgentWakeRecord | None: ...

    async def list_wakes(self, *, target_run_id: str | None = None) -> tuple[GovernedAgentWakeRecord, ...]: ...


class GovernedAgentWakeControlRepository(Protocol):
    async def apply_cancellation(
        self,
        request: GovernedAgentWakeCancellationRequest,
    ) -> GovernedAgentWakeControlResult: ...

    async def apply_recovery(
        self,
        request: GovernedAgentWakeRecoveryRequest,
    ) -> GovernedAgentWakeControlResult: ...

    async def list_actions(self, *, wake_id: str) -> tuple[GovernedAgentWakeActionRecord, ...]: ...
