from pathlib import Path

import pytest

from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate


def _executor(tmp_path: Path) -> TurnExecutor:
    return TurnExecutor(
        state_machine=StateMachine(),
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        workspace=tmp_path,
    )


def test_turn_executor_direct_helpers_are_not_redelegated(tmp_path):
    """Layer: unit. Verifies explicit helper methods are not also exposed through the `__getattr__` fallback."""
    executor = _executor(tmp_path)

    with pytest.raises(AttributeError):
        executor.__getattr__("_prepare_messages")
    with pytest.raises(AttributeError):
        executor.__getattr__("_parse_response")
    with pytest.raises(AttributeError):
        executor.__getattr__("_execute_tools")


def test_turn_executor_still_delegates_non_explicit_helpers(tmp_path):
    """Layer: unit. Verifies `__getattr__` still exposes the non-explicit delegated helper surface."""
    executor = _executor(tmp_path)

    assert callable(executor.__getattr__("_non_json_residue"))
