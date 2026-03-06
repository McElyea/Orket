from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.runtime.error_codes import ERR_JSON_MD_FENCE, ERR_THINK_OVERFLOW, EXTRANEOUS_TEXT
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


def test_contract_validator_allows_recovered_truncated_tool_only_payload(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='```json\n{"tool":"write_file","args":{"path":"a.txt","content":"ok"}\n```',
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.consistency_scope_diagnostics(
        turn,
        context={"verification_scope": {"consistency_tool_calls_only": True}},
    )
    assert diagnostics["violations"] == []


def test_contract_validator_rejects_prefixed_prose_even_with_recovered_tool_call(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='I will now comply: {"tool":"write_file","args":{"path":"a.txt","content":"ok"}',
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.consistency_scope_diagnostics(
        turn,
        context={"verification_scope": {"consistency_tool_calls_only": True}},
    )
    assert diagnostics["violations"]
    assert diagnostics["violations"][0]["rule_id"] == "CONSISTENCY.OUTPUT_FORMAT"


def test_contract_validator_allows_think_prefixed_tool_only_payload(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content=(
            '<think>I should only emit tool calls.</think>'
            '{"tool":"write_file","args":{"path":"a.txt","content":"ok"}}'
        ),
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.consistency_scope_diagnostics(
        turn,
        context={"verification_scope": {"consistency_tool_calls_only": True}},
    )
    assert diagnostics["violations"] == []


def test_contract_validator_allows_thinking_process_prefixed_tool_only_payload(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content=(
            "Thinking Process: first I inspect the task.\n"
            '{"tool":"write_file","args":{"path":"a.txt","content":"ok"}}'
        ),
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.consistency_scope_diagnostics(
        turn,
        context={"verification_scope": {"consistency_tool_calls_only": True}},
    )
    assert diagnostics["violations"] == []


def test_contract_validator_local_prompt_reports_markdown_fence_leaf_code(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='```json\n{"ok":true}\n```',
        raw={"task_class": "strict_json"},
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(turn, context={})

    violation = next(item for item in diagnostics["violations"] if item["rule_id"] == "LOCAL_PROMPT.MARKDOWN_FENCE")
    assert violation["error_code"] == ERR_JSON_MD_FENCE
    assert violation["error_family"] == EXTRANEOUS_TEXT


def test_contract_validator_local_prompt_allows_leading_think_block_when_profile_permits(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="<think>plan</think>\n{\"ok\":true}",
        raw={
            "task_class": "strict_json",
            "local_prompt_allows_thinking_blocks": True,
            "local_prompt_thinking_block_format": "xml_think_tags",
        },
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(turn, context={})
    assert diagnostics["violations"] == []


def test_contract_validator_local_prompt_rejects_think_block_after_payload(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='{"ok":true}<think>extra</think>',
        raw={
            "task_class": "strict_json",
            "local_prompt_allows_thinking_blocks": True,
            "local_prompt_thinking_block_format": "xml_think_tags",
        },
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(turn, context={})

    think_violation = next(item for item in diagnostics["violations"] if item["rule_id"] == "LOCAL_PROMPT.THINK_POSITION")
    assert think_violation["error_code"] == ERR_THINK_OVERFLOW


def test_contract_validator_local_prompt_rejects_profile_intro_denylist_prefix(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='Sure {"ok":true}',
        raw={
            "task_class": "strict_json",
            "local_prompt_intro_denylist": ["sure"],
        },
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(turn, context={})
    assert any(item["rule_id"] == "LOCAL_PROMPT.INTRO_DENYLIST" for item in diagnostics["violations"])
