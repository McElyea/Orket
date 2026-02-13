import pytest

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.core.types import CardStatus, CardType


def test_guard_waiting_transition_allowed():
    assert StateMachine.validate_transition(
        CardType.ISSUE,
        CardStatus.CODE_REVIEW,
        CardStatus.AWAITING_GUARD_REVIEW,
        roles=["developer"],
    )


def test_guard_decision_requires_integrity_guard():
    with pytest.raises(StateMachineError):
        StateMachine.validate_transition(
            CardType.ISSUE,
            CardStatus.AWAITING_GUARD_REVIEW,
            CardStatus.GUARD_APPROVED,
            roles=["developer"],
        )


def test_guard_decision_allowed_for_integrity_guard():
    assert StateMachine.validate_transition(
        CardType.ISSUE,
        CardStatus.AWAITING_GUARD_REVIEW,
        CardStatus.GUARD_APPROVED,
        roles=["integrity_guard"],
    )
