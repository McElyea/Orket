from typing import List, Dict, Set, Optional, Union
from orket.schema import CardStatus, CardType, WaitReason

class StateMachineError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

class StateMachine:
    """
    Mechanical Enforcer for Card state transitions.
    Defines the 'Allowed Path' for every work unit in the engine.
    """
    
    # Define valid transitions for each Card Type
    _TRANSITIONS: Dict[CardType, Dict[CardStatus, Set[CardStatus]]] = {
        CardType.ISSUE: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.IN_PROGRESS: {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER, CardStatus.READY_FOR_TESTING, CardStatus.CODE_REVIEW, CardStatus.CANCELED},
            CardStatus.BLOCKED: {CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.WAITING_FOR_DEVELOPER: {CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.READY_FOR_TESTING: {CardStatus.CODE_REVIEW, CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.CODE_REVIEW: {CardStatus.DONE, CardStatus.IN_PROGRESS, CardStatus.READY_FOR_TESTING},
            CardStatus.DONE: set(), # Final State
            CardStatus.CANCELED: set() # Final State
        },
        CardType.EPIC: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.IN_PROGRESS: {CardStatus.CODE_REVIEW, CardStatus.DONE, CardStatus.CANCELED},
            CardStatus.CODE_REVIEW: {CardStatus.DONE, CardStatus.IN_PROGRESS},
            CardStatus.DONE: set(),
            CardStatus.CANCELED: set()
        },
        CardType.ROCK: {
            CardStatus.READY: {CardStatus.IN_PROGRESS, CardStatus.CANCELED},
            CardStatus.IN_PROGRESS: {CardStatus.DONE, CardStatus.CANCELED},
            CardStatus.DONE: set(),
            CardStatus.CANCELED: set()
        }
    }

    @staticmethod
    def validate_transition(
        card_type: CardType,
        current: CardStatus,
        requested: CardStatus,
        roles: Union[str, List[str]] = "system",
        wait_reason: Optional[WaitReason] = None
    ):
        """
        Validates if a set of roles is allowed to perform a specific state change.
        Enforces mechanical governance (e.g. only Verifiers can move to DONE).
        Requires wait_reason when transitioning to BLOCKED or WAITING_FOR_DEVELOPER.
        """

        # Normalize roles to a list
        role_list = [roles] if isinstance(roles, str) else roles

        # 1. Check if the transition exists in the map
        allowed_next = StateMachine._TRANSITIONS.get(card_type, {}).get(current, set())

        if requested not in allowed_next:
            raise StateMachineError(f"Invalid transition for {card_type}: {current.value} -> {requested.value}")

        # 2. Wait Reason Enforcement (The 'Diagnostic' Gate)
        if requested in {CardStatus.BLOCKED, CardStatus.WAITING_FOR_DEVELOPER}:
            if wait_reason is None:
                raise StateMachineError(
                    f"wait_reason is required when transitioning to {requested.value}. "
                    f"Valid reasons: {[r.value for r in WaitReason]}"
                )

        # 3. Role-Based Enforcement (The 'Integrity' Gate)
        if card_type == CardType.ISSUE:
            # Only an 'integrity_guard' (Verifier) can move an issue to DONE
            if requested == CardStatus.DONE and "integrity_guard" not in role_list:
                raise StateMachineError(f"Permission Denied: Only the 'integrity_guard' role can finalize Issues to 'DONE'. Current roles: {role_list}")

        return True