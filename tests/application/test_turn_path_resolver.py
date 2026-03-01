from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_path_resolver import PathResolver
from orket.domain.execution import ExecutionTurn, ToolCall


def test_partition_required_read_paths_splits_existing_and_missing(tmp_path: Path) -> None:
    existing_file = tmp_path / "agent_output" / "main.py"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("print('ok')\n", encoding="utf-8")
    context = {
        "required_read_paths": ["agent_output/main.py", "agent_output/missing.py", "  "],
    }

    existing, missing = PathResolver.partition_required_read_paths(context, tmp_path)

    assert existing == ["agent_output/main.py"]
    assert missing == ["agent_output/missing.py"]


def test_required_path_helpers_delegate_to_partition(tmp_path: Path) -> None:
    file_path = tmp_path / "agent_output" / "requirements.txt"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text("x\n", encoding="utf-8")
    context = {"required_read_paths": ["agent_output/requirements.txt", "agent_output/nope.txt"]}

    assert PathResolver.required_read_paths(context, tmp_path) == ["agent_output/requirements.txt"]
    assert PathResolver.missing_required_read_paths(context, tmp_path) == ["agent_output/nope.txt"]


def test_required_write_and_observed_paths() -> None:
    turn = ExecutionTurn(
        issue_id="ISSUE-1",
        role="coder",
        content="{}",
        tool_calls=[
            ToolCall(tool="read_file", args={"path": "agent_output/main.py"}, result=None, error=None),
            ToolCall(tool="write_file", args={"path": "agent_output/main.py"}, result=None, error=None),
            ToolCall(tool="list_dir", args={"path": "."}, result=None, error=None),
        ],
        raw={},
    )

    assert PathResolver.required_write_paths({"required_write_paths": ["agent_output/main.py", ""]}) == [
        "agent_output/main.py"
    ]
    assert PathResolver.observed_read_paths(turn) == ["agent_output/main.py"]
    assert PathResolver.observed_write_paths(turn) == ["agent_output/main.py"]
