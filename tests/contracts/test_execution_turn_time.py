"""Layer: contract. Turn values cannot invent an observation time."""
from dataclasses import asdict
from datetime import UTC, datetime

import pytest

from orket.core.domain.execution import ExecutionTurn

pytestmark = pytest.mark.contract


def test_turn_requires_an_explicit_timestamp_or_absence() -> None:
    with pytest.raises(TypeError, match="timestamp"):
        ExecutionTurn(role="developer", issue_id="ISSUE-1")


def test_identical_turn_inputs_have_identical_values() -> None:
    timestamp = datetime(2026, 9, 18, 12, 30, tzinfo=UTC)
    first = ExecutionTurn(role="developer", issue_id="ISSUE-1", timestamp=timestamp)
    second = ExecutionTurn(role="developer", issue_id="ISSUE-1", timestamp=timestamp)
    assert asdict(first) == asdict(second)
    assert first.timestamp == timestamp


def test_absent_turn_time_stays_absent() -> None:
    turn = ExecutionTurn(role="developer", issue_id="ISSUE-1", timestamp=None)
    assert asdict(turn)["timestamp"] is None
