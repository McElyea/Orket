from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_contract_validator import ContractValidator
from orket.application.workflows.turn_response_parser import ResponseParser
from orket.core.domain.execution import ExecutionTurn, ToolCall
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


def test_contract_validator_rejects_blank_required_write_content(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        tool_calls=[
            ToolCall(tool="write_file", args={"path": "agent_output/main.py", "content": ""}),
            ToolCall(tool="update_issue_status", args={"status": "done"}),
        ],
    )
    context = {
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_write_paths": ["agent_output/main.py"],
    }

    violations = validator.collect_contract_violations(turn, _role(), context)

    assert any(item["reason"] == "write_content_contract_not_met" for item in violations)


def test_contract_validator_rejects_artifact_semantic_contract_violations(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        tool_calls=[
            ToolCall(
                tool="write_file",
                args={
                    "path": "agent_output/main.py",
                    "content": "from .challenge_runtime.cli import main\n",
                },
            ),
            ToolCall(tool="update_issue_status", args={"status": "done"}),
        ],
    )
    context = {
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_write_paths": ["agent_output/main.py"],
        "artifact_contract": {
            "semantic_checks": [
                {
                    "path": "agent_output/main.py",
                    "label": "script entrypoint imports",
                    "must_contain": ["from challenge_runtime"],
                    "must_not_contain": ["from .challenge_runtime"],
                }
            ]
        },
    }

    violations = validator.collect_contract_violations(turn, _role(), context)

    semantic_violation = next(item for item in violations if item["reason"] == "artifact_semantic_contract_not_met")
    assert semantic_violation["violations"][0]["path"] == "agent_output/main.py"
    assert semantic_violation["violations"][0]["missing_tokens"] == ["from challenge_runtime"]
    assert semantic_violation["violations"][0]["forbidden_tokens"] == ["from .challenge_runtime"]
    assert semantic_violation["violations"][0]["preserve_tokens"] == []


def test_contract_validator_reports_high_specificity_preserve_tokens_for_semantic_retry(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        tool_calls=[
            ToolCall(
                tool="write_file",
                args={
                    "path": "agent_output/tests/test_validator_and_planner.py",
                    "content": (
                        "workflow_path.write_text(json.dumps(workflow), encoding='utf-8')\n"
                        "errors = validate_workflow(str(workflow_path))\n"
                    ),
                },
            ),
            ToolCall(tool="update_issue_status", args={"status": "done"}),
        ],
    )
    context = {
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_write_paths": ["agent_output/tests/test_validator_and_planner.py"],
        "artifact_contract": {
            "semantic_checks": [
                {
                    "path": "agent_output/tests/test_validator_and_planner.py",
                    "label": "validator and planner tests use real fixture paths",
                    "must_contain": [
                        "write_text(json.dumps(",
                        "validate_workflow(str(",
                        "plan_workflow(str(",
                    ],
                    "must_not_contain": [],
                }
            ]
        },
    }

    violations = validator.collect_contract_violations(turn, _role(), context)

    semantic_violation = next(item for item in violations if item["reason"] == "artifact_semantic_contract_not_met")
    assert semantic_violation["violations"][0]["missing_tokens"] == ["plan_workflow(str("]
    assert semantic_violation["violations"][0]["preserve_tokens"] == ["write_text(json.dumps("]


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


def test_contract_validator_allows_recovered_quote_heavy_legacy_tool_only_payload(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content=(
            '```json\n'
            '{\n'
            '  "tool": "write_file",\n'
            '  "args": {\n'
            '    "path": "agent_output/challenge_runtime/validator.py",\n'
            '    "content": "if task[\'duration\'] < 0:\\n'
            '    errors.append({\\n'
            '        \'message\': f\'Negative duration: {task["duration"]}\'\\n'
            '    })"\n'
            '  }\n'
            '}\n'
            '```\n\n'
            '```json\n'
            '{\n'
            '  "tool": "update_issue_status",\n'
            '  "args": {\n'
            '    "status": "code_review"\n'
            '  }\n'
            '}\n'
            '```'
        ),
        tool_calls=[
            ToolCall(
                tool="write_file",
                args={"path": "agent_output/challenge_runtime/validator.py", "content": "placeholder"},
            ),
            ToolCall(tool="update_issue_status", args={"status": "code_review"}),
        ],
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
    """Layer: contract. Verifies protocol-governed local prompting rejects fenced JSON payloads."""
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='```json\n{"ok":true}\n```',
        raw={"task_class": "strict_json"},
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(
        turn,
        context={"protocol_governed_enabled": True},
    )

    violation = next(item for item in diagnostics["violations"] if item["rule_id"] == "LOCAL_PROMPT.MARKDOWN_FENCE")
    assert violation["error_code"] == ERR_JSON_MD_FENCE
    assert violation["error_family"] == EXTRANEOUS_TEXT


def test_contract_validator_local_prompt_rejects_markdown_fence_on_legacy_non_protocol_tool_path(tmp_path: Path) -> None:
    """Layer: contract. Verifies legacy tool-call turns reject fenced JSON blocks instead of relying on repair."""
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='```json\n{"tool":"write_file","args":{"path":"a.txt","content":"ok"}}\n```',
        raw={"task_class": "tool_call"},
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )

    diagnostics = validator.local_prompt_anti_meta_diagnostics(
        turn,
        context={"protocol_governed_enabled": False},
    )

    fence_violation = next(item for item in diagnostics["violations"] if item["rule_id"] == "LOCAL_PROMPT.MARKDOWN_FENCE")
    assert fence_violation["error_code"] == ERR_JSON_MD_FENCE


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


def test_contract_validator_local_prompt_rejects_tool_call_meta_prefix_from_profile_denylist(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content='Thinking Process:\n{"tool":"write_file","args":{"path":"a.txt","content":"ok"}}',
        raw={
            "task_class": "tool_call",
            "local_prompt_intro_denylist": ["thinking process:"],
        },
        tool_calls=[ToolCall(tool="write_file", args={"path": "a.txt", "content": "ok"})],
    )
    diagnostics = validator.local_prompt_anti_meta_diagnostics(
        turn,
        context={"protocol_governed_enabled": False},
    )

    violation = next(item for item in diagnostics["violations"] if item["rule_id"] == "LOCAL_PROMPT.INTRO_DENYLIST")
    assert violation["detail"] == "thinking process:"


def test_contract_validator_accepts_comment_contract_when_comment_is_structured(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    turn = ExecutionTurn(
        role="reviewer",
        issue_id="ISSUE-2",
        tool_calls=[
            ToolCall(
                tool="add_issue_comment",
                args={
                    "comment": (
                        "Findings: the scaffold is path-stable.\n"
                        "Severity: low.\n"
                        "Path: agent_output/main.py.\n"
                        "Evidence: reviewed the entrypoint and output contract in detail."
                    )
                },
            )
        ],
    )

    diagnostics = validator.comment_contract_diagnostics(
        turn,
        context={
            "required_action_tools": ["add_issue_comment"],
            "required_comment_min_length": 80,
            "required_comment_contains": ["Findings", "Severity", "Path"],
            "required_read_paths": ["agent_output/main.py"],
        },
    )

    assert diagnostics["ok"] is True
    assert diagnostics["missing_comment_paths"] == []


def test_contract_validator_rejects_comment_contract_when_terms_are_missing(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    agent_output = tmp_path / "agent_output"
    agent_output.mkdir(parents=True, exist_ok=True)
    (agent_output / "main.py").write_text("print('ok')\n", encoding="utf-8")
    turn = ExecutionTurn(
        role="reviewer",
        issue_id="ISSUE-3",
        tool_calls=[ToolCall(tool="add_issue_comment", args={"comment": "Need more detail."})],
    )

    diagnostics = validator.comment_contract_diagnostics(
        turn,
        context={
            "required_action_tools": ["add_issue_comment"],
            "required_comment_min_length": 40,
            "required_comment_contains": ["Findings", "Severity", "Path"],
            "required_read_paths": ["agent_output/main.py"],
        },
    )

    assert diagnostics["ok"] is False
    assert diagnostics["missing_comment_terms"] == ["Findings", "Severity", "Path"]
    assert diagnostics["missing_comment_paths"] == ["agent_output/main.py"]


def test_contract_validator_rejects_comment_contract_when_required_paths_are_not_cited(tmp_path: Path) -> None:
    validator = _validator(tmp_path)
    ui_dir = tmp_path / "agent_output" / "soak_matrix" / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    (ui_dir / "operator_panel.md").write_text("# Operator Panel\n", encoding="utf-8")
    (ui_dir / "style_notes.md").write_text("# Style Notes\n", encoding="utf-8")
    turn = ExecutionTurn(
        role="reviewer",
        issue_id="ISSUE-4",
        tool_calls=[
            ToolCall(
                tool="add_issue_comment",
                args={
                    "comment": (
                        "Findings: review completed.\n"
                        "Severity: medium.\n"
                        "Path: cited one file only.\n"
                        "Evidence: grounded on the operator panel and style notes."
                    )
                },
            )
        ],
    )

    diagnostics = validator.comment_contract_diagnostics(
        turn,
        context={
            "required_action_tools": ["add_issue_comment"],
            "required_comment_min_length": 80,
            "required_comment_contains": ["Findings", "Severity", "Path"],
            "required_read_paths": [
                "agent_output/soak_matrix/ui/operator_panel.md",
                "agent_output/soak_matrix/ui/style_notes.md",
            ],
        },
    )

    assert diagnostics["ok"] is False
    assert diagnostics["missing_comment_terms"] == []
    assert diagnostics["missing_comment_paths"] == [
        "agent_output/soak_matrix/ui/operator_panel.md",
        "agent_output/soak_matrix/ui/style_notes.md",
    ]
