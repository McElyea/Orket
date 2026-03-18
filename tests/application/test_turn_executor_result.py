from __future__ import annotations

import pytest

from orket.application.workflows.turn_executor import TurnResult

pytestmark = pytest.mark.unit


def test_turn_result_failed_defaults_to_iterable_empty_violations() -> None:
    result = TurnResult.failed("some error")

    assert result.violations == []
    assert list(result.violations) == []
