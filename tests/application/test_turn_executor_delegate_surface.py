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
    """Layer: unit. Verifies the coordinator keeps real helper methods without a magic delegate surface."""
    executor = _executor(tmp_path)

    assert callable(executor._prepare_messages)
    assert callable(executor._parse_response)
    assert callable(executor._execute_tools)


def test_turn_executor_legacy_delegate_names_are_not_attributes(tmp_path):
    """Layer: unit. Verifies former facade-only helper names are no longer hidden on the executor itself."""
    executor = _executor(tmp_path)

    with pytest.raises(AttributeError):
        getattr(executor, "_non_json_residue")
    with pytest.raises(AttributeError):
        getattr(executor, "_collect_contract_violations")
    with pytest.raises(AttributeError):
        getattr(executor, "_append_memory_event")


def test_turn_executor_exposes_collaborators_explicitly(tmp_path):
    """Layer: unit. Verifies the seam is inspectable through explicit collaborators."""
    executor = _executor(tmp_path)

    assert not hasattr(TurnExecutor, "__getattr__")
    assert callable(executor.response_parser.non_json_residue)
    assert callable(executor.contract_validator.collect_contract_violations)
    assert callable(executor.corrective_prompt_builder.build_corrective_instruction)
    assert callable(executor.artifact_writer.append_memory_event)
