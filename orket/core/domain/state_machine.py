from typing import List, Dict, Set, Optional, Union

from orket.schema import CardStatus, CardType, WaitReason


class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""


class StateMachine:
    """
    Mechanical Enforcer for Card state transitions.
    Defines the allowed path for every work unit.
    """

    _TRANSITIONS: Dict[CardType, Dict[CardStatus, Set[CardStatus]]] = {
        CardType.ISSUE: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.IN_PROGRESS: {
                CardStatus.BLOCKED,
                CardStatus.WAITING_FOR_DEVELOPER,
                CardStatus.READY_FOR_TESTING,
                CardStatus.CODE_REVIEW,
                CardStatus.CANCELED,
                CardStatus.ARCHIVED,
            },
            CardStatus.BLOCKED: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.WAITING_FOR_DEVELOPER: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.READY_FOR_TESTING: {
                CardStatus.CODE_REVIEW,
                CardStatus.IN_PROGRESS,
                CardStatus.CANCELED,
                CardStatus.ARCHIVED,
            },
            CardStatus.CODE_REVIEW: {
                CardStatus.DONE,
                CardStatus.IN_PROGRESS,
                CardStatus.READY_FOR_TESTING,
                CardStatus.ARCHIVED,
            },
            CardStatus.DONE: {CardStatus.ARCHIVED},
            CardStatus.CANCELED: {CardStatus.ARCHIVED},
            CardStatus.ARCHIVED: set(),
        },
        CardType.EPIC: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.IN_PROGRESS: {CardStatus.CODE_REVIEW, CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.CODE_REVIEW: {CardStatus.DONE, CardStatus.IN_PROGRESS, CardStatus.ARCHIVED},
            CardStatus.DONE: {CardStatus.ARCHIVED},
            CardStatus.CANCELED: {CardStatus.ARCHIVED},
            CardStatus.ARCHIVED: set(),
        },
        CardType.ROCK: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.IN_PROGRESS: {CardStatus.DONE, CardStatus.CANCELED, CardStatus.ARCHIVED},
            CardStatus.DONE: {CardStatus.ARCHIVED},
            CardStatus.CANCELED: {CardStatus.ARCHIVED},
            CardStatus.ARCHIVED: set(),
        },
    }

    @staticmethod
    def validate_transition(
        card_type: CardType,
        current: CardStatus,
        requested: CardStatus,
        roles: Union[str, List[str]] = "system",
        wait_reason: Optional[WaitReason] = None,
    ):
        role_list = [roles] if isinstance(roles, str) else roles
        allowed_next = StateMachine._TRANSITIONS.get(card_type, {}).get(current, set())

        if requested not in allowed_next:
            raise StateMachineError(f"Invalid transition for {card_type}: {current.value} -> {requested.value}")

        if requested in {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER} and wait_reason is None:
            raise StateMachineError(
                f"wait_reason is required when transitioning to {requested.value}. "
                f"Valid reasons: {[r.value for r in WaitReason]}"
            )

        if card_type == CardType.ISSUE and requested == CardStatus.DONE and "integrity_guard" not in role_list:
            raise StateMachineError(
                "Permission Denied: Only the 'integrity_guard' role can finalize "
                f"Issues to 'DONE'. Current roles: {role_list}"
            )

        return True

