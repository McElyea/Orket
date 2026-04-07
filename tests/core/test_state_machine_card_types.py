# Layer: unit

from __future__ import annotations

import pytest

from orket.core.domain.state_machine import StateMachine, StateMachineError
from orket.schema import CardStatus, CardType


@pytest.mark.parametrize("card_type", [CardType.UTILITY, CardType.APP])
def test_simple_card_types_allow_ready_to_done_lifecycle(card_type: CardType) -> None:
    assert StateMachine.validate_transition(
        card_type,
        CardStatus.READY,
        CardStatus.IN_PROGRESS,
    )
    assert StateMachine.validate_transition(
        card_type,
        CardStatus.IN_PROGRESS,
        CardStatus.DONE,
    )
    assert StateMachine.validate_transition(
        card_type,
        CardStatus.DONE,
        CardStatus.ARCHIVED,
    )


@pytest.mark.parametrize("card_type", [CardType.UTILITY, CardType.APP])
def test_simple_card_types_reject_direct_ready_to_done(card_type: CardType) -> None:
    with pytest.raises(StateMachineError):
        StateMachine.validate_transition(
            card_type,
            CardStatus.READY,
            CardStatus.DONE,
        )
