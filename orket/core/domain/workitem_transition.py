from __future__ import annotations

from collections.abc import Iterable
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, Field

from orket.core.domain.workflow_profiles import resolve_workflow_profile
from orket.schema import CardStatus, CardType


class TransitionErrorCode(str, Enum):
    INVALID_ACTION = "INVALID_ACTION"
    DEPENDENCY_UNRESOLVED = "DEPENDENCY_UNRESOLVED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    INVARIANT_FAILED = "INVARIANT_FAILED"


class TransitionResult(BaseModel):
    ok: bool
    action: str
    new_status: str | None = None
    error_code: TransitionErrorCode | None = None
    error: str | None = None
    gate_request_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class TransitionGateBoundary(Protocol):
    def pre_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        requested_status: CardStatus,
        payload: dict[str, Any],
    ) -> TransitionResult | None: ...

    def post_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        requested_status: CardStatus,
        payload: dict[str, Any],
    ) -> TransitionResult | None: ...


class WorkItemTransitionService:
    """
    Profile-agnostic transition boundary for lifecycle mutations.
    v1 supports a compatibility action (`set_status`) while preserving
    deterministic result/error envelopes for callers.
    """

    def __init__(
        self,
        *,
        workflow_profile: str = "legacy_cards_v1",
        gate_boundary: TransitionGateBoundary | None = None,
    ) -> None:
        self.profile = resolve_workflow_profile(workflow_profile)
        self.workflow_profile = self.profile.name
        self.gate_boundary = gate_boundary

    @staticmethod
    def _is_system_retry_requeue(
        *,
        action: str,
        current_status: CardStatus,
        requested_status: CardStatus,
        payload: dict[str, Any],
    ) -> bool:
        if action != "system_set_status":
            return False
        if current_status != CardStatus.IN_PROGRESS or requested_status != CardStatus.READY:
            return False
        reason = str((payload or {}).get("reason", "")).strip().lower()
        return reason in {"retry_scheduled", "runtime_guard_retry_scheduled"}

    def request_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        payload: dict[str, Any] | None = None,
        roles: Iterable[str] | None = None,
        card_type: CardType = CardType.ISSUE,
    ) -> TransitionResult:
        payload = payload or {}
        normalized_action = str(action or "").strip().lower()
        if not normalized_action:
            return TransitionResult(
                ok=False,
                action=normalized_action,
                error_code=TransitionErrorCode.INVALID_ACTION,
                error="Missing action.",
            )

        metadata: dict[str, Any] = {"workflow_profile": self.workflow_profile}
        requested: CardStatus | None
        if normalized_action == "system_set_status":
            target = str(payload.get("status", "")).strip().lower()
            reason = str(payload.get("reason", "")).strip()
            if not target:
                return TransitionResult(
                    ok=False,
                    action=normalized_action,
                    error_code=TransitionErrorCode.INVALID_ACTION,
                    error="Missing status for system_set_status.",
                )
            if not reason:
                return TransitionResult(
                    ok=False,
                    action=normalized_action,
                    error_code=TransitionErrorCode.INVARIANT_FAILED,
                    error="system_set_status requires a non-empty reason.",
                )
            try:
                requested = CardStatus(target)
            except ValueError:
                return TransitionResult(
                    ok=False,
                    action=normalized_action,
                    error_code=TransitionErrorCode.INVALID_ACTION,
                    error=f"Unknown status: {target}",
                )
            metadata["policy_override"] = True
            metadata["override_reason"] = reason
        else:
            requested = self.profile.resolve_requested_status(normalized_action, payload)
        if requested is None:
            return TransitionResult(
                ok=False,
                action=normalized_action,
                error_code=TransitionErrorCode.INVALID_ACTION,
                error=f"Unknown action: {normalized_action}",
            )

        unresolved = [str(item) for item in (payload.get("unresolved_dependencies") or []) if str(item).strip()]
        if unresolved and requested not in {
            CardStatus.DONE,
            CardStatus.CANCELED,
            CardStatus.ARCHIVED,
            CardStatus.GUARD_APPROVED,
        }:
            return TransitionResult(
                ok=False,
                action=normalized_action,
                error_code=TransitionErrorCode.DEPENDENCY_UNRESOLVED,
                error="Unresolved dependencies prevent transition.",
                metadata={"unresolved_dependencies": unresolved},
            )

        if self.gate_boundary is not None:
            pre_result = self.gate_boundary.pre_transition(
                action=normalized_action,
                current_status=current_status,
                requested_status=requested,
                payload=payload,
            )
            if pre_result is not None and not pre_result.ok:
                return pre_result

        check = self.profile.validate_transition(
            card_type=card_type,
            current=current_status,
            requested=requested,
            roles=[str(role).strip() for role in (roles or []) if str(role).strip()],
            payload=payload,
        )
        if not check.ok:
            if self._is_system_retry_requeue(
                action=normalized_action,
                current_status=current_status,
                requested_status=requested,
                payload=payload,
            ):
                metadata["system_retry_requeue"] = True
            else:
                return TransitionResult(
                    ok=False,
                    action=normalized_action,
                    error_code=TransitionErrorCode.POLICY_VIOLATION,
                    error=str(check.error or "Transition rejected by workflow policy."),
                )

        result = TransitionResult(
            ok=True,
            action=normalized_action,
            new_status=requested.value,
            metadata=metadata,
        )
        if self.gate_boundary is not None:
            post_result = self.gate_boundary.post_transition(
                action=normalized_action,
                current_status=current_status,
                requested_status=requested,
                payload=payload,
            )
            if post_result is not None and not post_result.ok:
                return post_result
        return result
