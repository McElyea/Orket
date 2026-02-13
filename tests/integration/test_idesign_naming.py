from pathlib import Path
from orket.services.idesign_validator import iDesignValidator, ViolationCode
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
    violations = iDesignValidator.validate_turn(turn, Path("."))
    assert len(violations) == 1
    assert violations[0].code == ViolationCode.NAMING_VIOLATION
    assert "Manager component" in violations[0].message

    # 2. Engine naming violation
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating an engine",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "engines/compute.py", "content": "..."})
        ]
    )
    violations = iDesignValidator.validate_turn(turn, Path("."))
    assert len(violations) == 1
    assert violations[0].code == ViolationCode.NAMING_VIOLATION
    assert "Engine component" in violations[0].message

    # 3. Valid naming
    turn = ExecutionTurn(
        role="lead_architect",
        issue_id="ISSUE-01",
        content="Creating a valid manager",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "managers/AuthManager.py", "content": "..."})
        ]
    )
    violations = iDesignValidator.validate_turn(turn, Path("."))
    assert len(violations) == 0

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
    violations = iDesignValidator.validate_turn(turn, Path("."))
    assert len(violations) == 1
    assert violations[0].code == ViolationCode.CATEGORY_VIOLATION
    assert "Unrecognized component category 'utilities'" in violations[0].message


