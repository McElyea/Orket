"""Layer: contract. Required-read validation predicate retention."""

from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_read_context import RequiredReadObservation
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.schema import RoleConfig
from tests.helpers.turn_artifacts import artifact_test_utc_now


def test_progress_predicate_retains_all_missing_required_read_refusal(tmp_path: Path) -> None:
    """Empty classification prunes display only, not the published action predicate."""
    validator = ContractValidator(ResponseParser(utc_now=artifact_test_utc_now))
    role = RoleConfig(
        id="REVIEW", summary="reviewer", description="Review", tools=["read_file"],
    )
    turn = ExecutionTurn(
        timestamp=None, role="reviewer", issue_id="ISSUE-MISSING",
        tool_calls=[ToolCall(tool="read_file", args={"path": "missing.txt"})],
    )
    diagnostics = validator.progress_contract_diagnostics(
        turn,
        role,
        {"required_action_tools": ["read_file"]},
        RequiredReadObservation(existing=(), missing=("missing.txt",)),
    )

    assert diagnostics["required_action_tools"] == []
    assert diagnostics["ok"] is False
