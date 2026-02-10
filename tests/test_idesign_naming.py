import pytest
from pathlib import Path
from orket.services.idesign_validator import iDesignValidator
from orket.domain.execution import ExecutionTurn, ToolCall

def test_idesign_naming_violations():
    # 1. Manager naming violation
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating a manager",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "managers/my_logic.py", "content": "..."})
        ]
    )
    violation = iDesignValidator.validate_turn(turn, Path("."))
    assert "Manager component" in violation
    assert "must include 'Manager' in the filename" in violation

    # 2. Engine naming violation
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating an engine",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "engines/compute.py", "content": "..."})
        ]
    )
    violation = iDesignValidator.validate_turn(turn, Path("."))
    assert "Engine component" in violation
    assert "must include 'Engine' in the filename" in violation

    # 3. Valid naming
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating a valid manager",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "managers/AuthManager.py", "content": "..."})
        ]
    )
    violation = iDesignValidator.validate_turn(turn, Path("."))
    assert violation is None

def test_idesign_allowed_categories():
    # 1. Invalid category
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating a generic file",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "utilities/helpers.py", "content": "..."})
        ]
    )
    violation = iDesignValidator.validate_turn(turn, Path("."))
    assert "Unrecognized component category 'utilities'" in violation
