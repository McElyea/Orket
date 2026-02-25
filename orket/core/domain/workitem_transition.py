from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Iterable, Optional, Protocol

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
    new_status: Optional[str] = None
    error_code: Optional[TransitionErrorCode] = None
    error: Optional[str] = None
    gate_request_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TransitionGateBoundary(Protocol):
    def pre_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        requested_status: CardStatus,
        payload: Dict[str, Any],
    ) -> TransitionResult | None:
        ...

    def post_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        requested_status: CardStatus,
        payload: Dict[str, Any],
    ) -> TransitionResult | None:
        ...


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
    ):
        self.profile = resolve_workflow_profile(workflow_profile)
        self.workflow_profile = self.profile.name
        self.gate_boundary = gate_boundary

    def request_transition(
        self,
        *,
        action: str,
        current_status: CardStatus,
        payload: Optional[Dict[str, Any]] = None,
        roles: Optional[Iterable[str]] = None,
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

        requested = self.profile.resolve_requested_status(normalized_action, payload)
        if requested is None:
            return TransitionResult(
                ok=False,
                action=normalized_action,
                error_code=TransitionErrorCode.INVALID_ACTION,
                error=f"Unknown action: {normalized_action}",
            )

        unresolved = [str(item) for item in (payload.get("unresolved_dependencies") or []) if str(item).strip()]
        if unresolved and requested not in {CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED, CardStatus.GUARD_APPROVED}:
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
            metadata={"workflow_profile": self.workflow_profile},
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
