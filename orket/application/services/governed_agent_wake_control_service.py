from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from orket.application.services.governed_agent_wake_records import (
    GovernedAgentWakeActionRecord,
    GovernedAgentWakeCancellationRequest,
    GovernedAgentWakeControlRepository,
    GovernedAgentWakeControlResult,
    GovernedAgentWakeRecoveryRequest,
    WakeRecoveryResolution,
)


class GovernedAgentWakeControlService:
    """Publish preconditioned wake controls through one durable repository."""

    def __init__(self, repository: GovernedAgentWakeControlRepository) -> None:
        self._repository = repository

    async def cancel(
        self,
        *,
        wake_id: str,
        payload: Mapping[str, Any],
    ) -> GovernedAgentWakeControlResult:
        allowed = {
            "action_id", "actor_ref", "timestamp_utc", "reason",
            "expected_cancellation_epoch", "cancellation_epoch",
        }
        _reject_unknown(payload, allowed)
        request = GovernedAgentWakeCancellationRequest(
            action_id=_required_text(payload.get("action_id")),
            wake_id=_required_text(wake_id),
            actor_ref=_required_text(payload.get("actor_ref")),
            timestamp_utc=_required_text(payload.get("timestamp_utc")),
            reason=_required_text(payload.get("reason")),
            expected_cancellation_epoch=_required_int(payload.get("expected_cancellation_epoch")),
            cancellation_epoch=_required_int(payload.get("cancellation_epoch")),
        )
        return await self._repository.apply_cancellation(request)

    async def recover(
        self,
        *,
        wake_id: str,
        payload: Mapping[str, Any],
    ) -> GovernedAgentWakeControlResult:
        allowed = {
            "action_id", "actor_ref", "timestamp_utc", "reason",
            "expected_fencing_generation", "resolution", "child_confirmed_stopped",
            "effect_uncertainty_cleared", "evidence_refs",
        }
        _reject_unknown(payload, allowed)
        resolution = str(payload.get("resolution") or "").strip()
        if resolution not in {"requeue", "confirm_cancelled"}:
            raise ValueError("E_AGENT_WAKE_RECOVERY_RESOLUTION_INVALID")
        request = GovernedAgentWakeRecoveryRequest(
            action_id=_required_text(payload.get("action_id")),
            wake_id=_required_text(wake_id),
            actor_ref=_required_text(payload.get("actor_ref")),
            timestamp_utc=_required_text(payload.get("timestamp_utc")),
            reason=_required_text(payload.get("reason")),
            expected_fencing_generation=_required_int(payload.get("expected_fencing_generation")),
            resolution=cast(WakeRecoveryResolution, resolution),
            child_confirmed_stopped=_required_bool(payload.get("child_confirmed_stopped")),
            effect_uncertainty_cleared=_required_bool(payload.get("effect_uncertainty_cleared")),
            evidence_refs=_text_sequence(payload.get("evidence_refs")),
        )
        return await self._repository.apply_recovery(request)

    async def list_actions(self, *, wake_id: str) -> tuple[GovernedAgentWakeActionRecord, ...]:
        return await self._repository.list_actions(wake_id=_required_text(wake_id))


def governed_agent_wake_action_view(action: GovernedAgentWakeActionRecord) -> dict[str, Any]:
    return {
        "action_id": action.action_id,
        "wake_id": action.wake_id,
        "action_kind": action.action_kind,
        "actor_ref": action.actor_ref,
        "timestamp_utc": action.timestamp_utc,
        "request": dict(action.request),
        "request_digest": action.request_digest,
        "status": action.status,
        "resulting_state": action.resulting_state,
        "resulting_fencing_generation": action.resulting_fencing_generation,
        "resulting_cancellation_epoch": action.resulting_cancellation_epoch,
        "resulting_uncertainty": action.resulting_uncertainty,
    }


def _reject_unknown(payload: Mapping[str, Any], allowed: set[str]) -> None:
    if set(payload) - allowed:
        raise ValueError("E_AGENT_WAKE_CONTROL_FIELD_UNKNOWN")


def _required_text(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("E_AGENT_WAKE_CONTROL_TEXT_REQUIRED")
    return normalized


def _required_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("E_AGENT_WAKE_CONTROL_INTEGER_REQUIRED")
    return value


def _required_bool(value: object) -> bool:
    if not isinstance(value, bool):
        raise ValueError("E_AGENT_WAKE_CONTROL_BOOLEAN_REQUIRED")
    return value


def _text_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("E_AGENT_WAKE_RECOVERY_EVIDENCE_REQUIRED")
    items = tuple(_required_text(item) for item in value)
    if not items:
        raise ValueError("E_AGENT_WAKE_RECOVERY_EVIDENCE_REQUIRED")
    return items
