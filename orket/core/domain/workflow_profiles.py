from __future__ import annotations

import contextlib
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType, WaitReason


@dataclass(frozen=True)
class TransitionCheckResult:
    ok: bool
    error: str | None = None


class WorkflowProfile(ABC):
    name: str

    @abstractmethod
    def resolve_requested_status(self, action: str, payload: dict[str, object]) -> CardStatus | None:
        raise NotImplementedError

    @abstractmethod
    def validate_transition(
        self,
        *,
        card_type: CardType,
        current: CardStatus,
        requested: CardStatus,
        roles: Iterable[str],
        payload: dict[str, object],
    ) -> TransitionCheckResult:
        raise NotImplementedError


class LegacyCardsV1Profile(WorkflowProfile):
    name = "legacy_cards_v1"

    _ACTION_TO_STATUS = {
        "start": CardStatus.IN_PROGRESS,
        "complete": CardStatus.DONE,
        "archive": CardStatus.ARCHIVED,
        "cancel": CardStatus.CANCELED,
        "send_to_review": CardStatus.CODE_REVIEW,
        "request_guard_review": CardStatus.AWAITING_GUARD_REVIEW,
    }

    def resolve_requested_status(self, action: str, payload: dict[str, object]) -> CardStatus | None:
        if action == "set_status":
            target = str(payload.get("status", "")).strip().lower()
            if not target:
                return None
            try:
                return CardStatus(target)
            except ValueError:
                return None
        return self._ACTION_TO_STATUS.get(action)

    def validate_transition(
        self,
        *,
        card_type: CardType,
        current: CardStatus,
        requested: CardStatus,
        roles: Iterable[str],
        payload: dict[str, object],
    ) -> TransitionCheckResult:
        raw_wait_reason = payload.get("wait_reason")
        wait_reason: WaitReason | None = None
        if isinstance(raw_wait_reason, WaitReason):
            wait_reason = raw_wait_reason
        elif isinstance(raw_wait_reason, str) and raw_wait_reason.strip():
            with contextlib.suppress(ValueError):
                wait_reason = WaitReason(raw_wait_reason.strip().lower())
        try:
            StateMachine.validate_transition(
                card_type=card_type,
                current=current,
                requested=requested,
                roles=[str(role).strip() for role in roles if str(role).strip()],
                wait_reason=wait_reason,
            )
            return TransitionCheckResult(ok=True)
        except StateMachineError as exc:
            return TransitionCheckResult(ok=False, error=str(exc))


class ProjectTaskV1Profile(WorkflowProfile):
    name = "project_task_v1"

    _ALLOWED_STATUSES = {
        CardStatus.READY,
        CardStatus.IN_PROGRESS,
        CardStatus.BLOCKED,
        CardStatus.DONE,
        CardStatus.CANCELED,
        CardStatus.ARCHIVED,
    }
    _TRANSITIONS: dict[CardStatus, set[CardStatus]] = {
        CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
        CardStatus.IN_PROGRESS: {CardStatus.BLOCKED, CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED},
        CardStatus.BLOCKED: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
        CardStatus.DONE: {CardStatus.ARCHIVED},
        CardStatus.CANCELED: {CardStatus.ARCHIVED},
        CardStatus.ARCHIVED: set(),
    }

    _ACTION_TO_STATUS = {
        "start": CardStatus.IN_PROGRESS,
        "block": CardStatus.BLOCKED,
        "complete": CardStatus.DONE,
        "archive": CardStatus.ARCHIVED,
        "cancel": CardStatus.CANCELED,
    }

    def resolve_requested_status(self, action: str, payload: dict[str, object]) -> CardStatus | None:
        if action == "set_status":
            target = str(payload.get("status", "")).strip().lower()
            if not target:
                return None
            try:
                requested = CardStatus(target)
            except ValueError:
                return None
            if requested not in self._ALLOWED_STATUSES:
                return None
            return requested
        return self._ACTION_TO_STATUS.get(action)

    def validate_transition(
        self,
        *,
        card_type: CardType,
        current: CardStatus,
        requested: CardStatus,
        roles: Iterable[str],
        payload: dict[str, object],
    ) -> TransitionCheckResult:
        allowed = self._TRANSITIONS.get(current, set())
        if requested not in allowed:
            return TransitionCheckResult(
                ok=False,
                error=f"Invalid transition in project_task_v1: {current.value} -> {requested.value}.",
            )
        if requested == CardStatus.BLOCKED and not str(payload.get("wait_reason", "")).strip():
            return TransitionCheckResult(ok=False, error="wait_reason is required for blocked status.")
        return TransitionCheckResult(ok=True)


def resolve_workflow_profile(name: str) -> WorkflowProfile:
    normalized = str(name or "").strip().lower()
    if normalized in {"", "legacy_cards_v1", "cards", "legacy"}:
        return LegacyCardsV1Profile()
    if normalized in {"project_task_v1", "project_task"}:
        return ProjectTaskV1Profile()
    raise ValueError(f"Unknown workflow profile: {name}")
