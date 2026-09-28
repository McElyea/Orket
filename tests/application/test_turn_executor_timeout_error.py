import pytest

from orket.application.workflows.turn_executor import ModelTimeoutError as TurnExecutorModelTimeoutError
from orket.exceptions import ModelTimeoutError as CanonicalModelTimeoutError

pytestmark = pytest.mark.contract


def test_turn_executor_exports_canonical_model_timeout_error() -> None:
    assert TurnExecutorModelTimeoutError is CanonicalModelTimeoutError
