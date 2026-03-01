from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.schema import RoleConfig


def _validator(tmp_path: Path) -> ContractValidator:
    parser = ResponseParser(tmp_path, lambda **_kwargs: None)
    return ContractValidator(tmp_path, parser)


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file", "update_issue_status"])


def test_contract_validator_collect_contract_violations_happy_path(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"}),
            ToolCall(tool="update_issue_status", args={"status": "done"}),
        ],
    )
    context = {
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_write_paths": ["agent_output/out.txt"],
    }
    assert validator.collect_contract_violations(turn, _role(), context) == []


def test_contract_validator_reports_consistency_scope_violation(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='{"tool":"write_file","args":{"path":"a.txt","content":"ok"}} extra prose',
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.consistency_scope_diagnostics(
        turn,
        context={"verification_scope": {"consistency_tool_calls_only": True}},
    )
    assert diagnostics["violations"]
    assert diagnostics["violations"][0]["rule_id"] == "CONSISTENCY.OUTPUT_FORMAT"
