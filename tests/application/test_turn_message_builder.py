from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", name="Demo", seat="coder", status="in_progress")


def _role() -> RoleConfig:
    return RoleConfig(id="coder", name="coder", description="Writes code", prompt="You are coder", tools=["write_file"])


async def test_message_builder_includes_execution_context(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "required_action_tools": ["write_file"],
        "required_statuses": ["done"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "history": [{"role": "user", "content": "prior"}],
    }
    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)
    assert "Execution Context JSON" in rendered
    assert "Write Path Contract" in rendered


async def test_message_builder_serializes_history_as_user_block(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "required_action_tools": [],
        "required_statuses": [],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [
            {"role": "coder", "content": "write main.py"},
            {"role": "integrity_guard", "content": "blocked: missing tests"},
        ],
    }
    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    history_messages = [m for m in messages if m.get("content", "").startswith("Prior Transcript JSON:\n")]
    assert len(history_messages) == 1
    assert history_messages[0]["role"] == "user"
    assert '"actor": "coder"' in history_messages[0]["content"]
    assert '"actor": "integrity_guard"' in history_messages[0]["content"]


async def test_message_builder_adds_protocol_response_contract_when_governed(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-1",
        "role": "coder",
        "protocol_governed_enabled": True,
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    protocol_messages = [m for m in messages if m.get("content", "").startswith("Protocol Response Contract:\n")]

    assert len(protocol_messages) == 1
    assert '"content":"","tool_calls"' in protocol_messages[0]["content"]
    assert "Do not use markdown fences" in protocol_messages[0]["content"]


async def test_message_builder_includes_issue_brief_fields(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    issue = IssueConfig(
        id="ISSUE-2",
        name="Operator packet",
        seat="product_owner",
        status="in_progress",
        description="Define operator-facing acceptance criteria.",
        requirements="Keep the output repo-local and truthful.",
        note="Write a brief and finish the turn with an explicit terminal status.",
        references=["docs/ROADMAP.md", "CURRENT_AUTHORITY.md"],
    )
    context = {
        "issue_id": "ISSUE-2",
        "role": "product_owner",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["done"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/brief.md"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=issue, role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Issue Brief:" in rendered
    assert "Description: Define operator-facing acceptance criteria." in rendered
    assert "Requirements: Keep the output repo-local and truthful." in rendered
    assert "Task Note: Write a brief and finish the turn with an explicit terminal status." in rendered
    assert "- docs/ROADMAP.md" in rendered
    assert "- CURRENT_AUTHORITY.md" in rendered


async def test_message_builder_preserves_issue_note_when_runtime_retry_note_is_present(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    issue = IssueConfig(
        id="ISSUE-2A",
        name="Runtime retry",
        seat="coder",
        status="in_progress",
        note="Keep dependency gating and truthful terminal states.",
    )
    context = {
        "issue_id": "ISSUE-2A",
        "role": "coder",
        "runtime_retry_note": "runtime_guard_retry_scheduled: timeout after 60s",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=issue, role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Task Note: Keep dependency gating and truthful terminal states." in rendered
    assert "Retry Note: runtime_guard_retry_scheduled: timeout after 60s" in rendered


async def test_message_builder_omits_issue_brief_for_guard_review_turn(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    issue = IssueConfig(
        id="ISSUE-3",
        name="Guard review",
        seat="product_owner",
        status="awaiting_guard_review",
        note="Builder instructions should not leak into guard review.",
    )
    role = RoleConfig(
        id="integrity_guard",
        name="integrity_guard",
        description="Finalize guard review",
        prompt="You are integrity guard",
        tools=["update_issue_status"],
    )
    context = {
        "issue_id": "ISSUE-3",
        "role": "integrity_guard",
        "current_status": "awaiting_guard_review",
        "required_action_tools": ["update_issue_status"],
        "required_statuses": ["done", "blocked"],
        "required_read_paths": [],
        "required_write_paths": [],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=issue, role=role, context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Issue Brief:" not in rendered
    assert "Builder instructions should not leak into guard review." not in rendered


async def test_message_builder_includes_comment_contract_when_required(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    required_path = tmp_path / "agent_output" / "requirements.txt"
    required_path.parent.mkdir(parents=True, exist_ok=True)
    required_path.write_text("repo-local soak goals\n", encoding="utf-8")
    context = {
        "issue_id": "ISSUE-4",
        "role": "reviewer",
        "required_action_tools": ["read_file", "add_issue_comment", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": [],
        "required_comment_min_length": 240,
        "required_comment_contains": ["Findings", "Severity", "Path"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Comment Contract:" in rendered
    assert "240 characters" in rendered
    assert "Findings, Severity, Path, agent_output/requirements.txt" in rendered
    assert "Cite every required read path by exact path string" in rendered
    assert "Exact required path tokens to cite: agent_output/requirements.txt" in rendered
    assert "A simple compliant citation pattern is: (agent_output/requirements.txt)." in rendered


async def test_message_builder_includes_runtime_verifier_contract_for_app_entrypoint(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5",
        "role": "coder",
        "required_action_tools": ["read_file", "write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": ["agent_output/main.py"],
        "artifact_contract": {
            "kind": "app",
            "entrypoint_path": "agent_output/main.py",
            "required_write_paths": ["agent_output/main.py"],
        },
        "runtime_verifier_contract": {
            "expect_json_stdout": True,
            "json_assertions": [
                {"path": "files_count", "op": "gte", "value": 1},
                {"path": "files_list", "op": "len_gte", "value": 1},
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Runtime Verifier Contract:" in rendered
    assert "python agent_output/main.py" in rendered
    assert "no positional arguments" in rendered
    assert "do not use package-relative imports" in rendered
    assert "must print valid JSON" in rendered
    assert "files_count gte 1" in rendered
    assert "files_list len_gte 1" in rendered


async def test_message_builder_includes_explicit_runtime_verifier_commands(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5A",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/README.md"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/README.md",
            "required_write_paths": ["agent_output/README.md"],
        },
        "runtime_verifier_contract": {
            "commands": [
                {"argv": ["python", "-m", "pytest", "-q", "tests"], "cwd": "agent_output"},
                {"argv": ["python", "agent_output/main.py"], "cwd": "."},
            ],
            "expect_json_stdout": True,
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Runtime Verifier Contract:" in rendered
    assert "cwd=agent_output: python -m pytest -q tests" in rendered
    assert "cwd=.: python agent_output/main.py" in rendered
    assert "stdout must print valid JSON" in rendered


async def test_message_builder_includes_runtime_verifier_contract_for_write_artifact_issue_override(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5A1",
        "role": "coder",
        "execution_profile": "write_artifact_v1",
        "profile_traits": {
            "intent": "write_artifact",
            "artifact_contract_required": True,
            "runtime_verifier_allowed": False,
        },
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/simulator.py",
            "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
        },
        "runtime_verifier_contract": {
            "commands": [
                {"argv": ["python", "-c", "print('artifact-proof')"], "cwd": "agent_output"},
            ],
            "expect_json_stdout": False,
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Runtime Verifier Contract:" in rendered
    assert "cwd=agent_output: python -c print('artifact-proof')" in rendered


async def test_message_builder_includes_artifact_semantic_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5B",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/main.py"],
        "artifact_contract": {
            "kind": "app",
            "entrypoint_path": "agent_output/main.py",
            "required_write_paths": ["agent_output/main.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/main.py",
                    "label": "script entrypoint imports",
                    "must_contain": ["from challenge_runtime"],
                    "must_not_contain": ["from .challenge_runtime"],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Artifact Semantic Contract:" in rendered
    assert "Path: agent_output/main.py" in rendered
    assert "Purpose: script entrypoint imports" in rendered
    assert "Must contain: from challenge_runtime" in rendered
    assert "Must not contain: from .challenge_runtime" in rendered


async def test_message_builder_includes_multi_tool_sequence_contract_for_legacy_prompts(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5A",
        "role": "coder",
        "required_action_tools": ["read_file", "write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": ["agent_output/main.py"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Emit multiple top-level JSON tool objects in sequence" in rendered


async def test_message_builder_suppresses_builder_contracts_for_review_comment_profile(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5B",
        "role": "reviewer",
        "execution_profile": "review_comment_v1",
        "profile_traits": {
            "intent": "review_comment",
            "artifact_contract_required": False,
            "runtime_verifier_allowed": False,
        },
        "required_action_tools": ["add_issue_comment", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": [],
        "artifact_contract": {
            "kind": "app",
            "entrypoint_path": "agent_output/main.py",
            "required_write_paths": ["agent_output/main.py"],
        },
        "runtime_verifier_contract": {
            "expect_json_stdout": True,
        },
        "scenario_truth": {
            "scenario_id": "role_matrix_soak_v1",
            "blocked_issue_policy": {
                "allowed_issue_ids": ["RMS-22"],
                "blocked_implies_run_failure": True,
            },
            "expected_terminal_status": "terminal_failure",
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Artifact Contract JSON:" not in rendered
    assert "Runtime Verifier Contract:" not in rendered
    assert "Scenario Truth Contract:" in rendered
    assert "role_matrix_soak_v1" in rendered
    assert "RMS-22" in rendered


async def test_message_builder_preloads_required_read_context(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    required_path = tmp_path / "agent_output" / "requirements.txt"
    required_path.parent.mkdir(parents=True, exist_ok=True)
    required_path.write_text("repo-local soak goals\n", encoding="utf-8")
    context = {
        "issue_id": "ISSUE-6",
        "role": "reviewer",
        "required_action_tools": ["read_file", "add_issue_comment", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": [],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Preloaded Read Context:" in rendered
    assert "Path: agent_output/requirements.txt" in rendered
    assert "repo-local soak goals" in rendered


async def test_message_builder_preloads_comment_grounding_without_read_tool_requirement(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    required_path = tmp_path / "agent_output" / "requirements.txt"
    required_path.parent.mkdir(parents=True, exist_ok=True)
    required_path.write_text("truthful failure detection\n", encoding="utf-8")
    context = {
        "issue_id": "ISSUE-7",
        "role": "reviewer",
        "required_action_tools": ["add_issue_comment", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": [],
        "required_comment_min_length": 120,
        "required_comment_contains": ["Findings"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Read Path Contract:" not in rendered
    assert "Preloaded Read Context:" in rendered
    assert "truthful failure detection" in rendered


async def test_message_builder_preloads_builder_grounding_without_read_tool_requirement(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    required_path = tmp_path / "agent_output" / "requirements.txt"
    required_path.parent.mkdir(parents=True, exist_ok=True)
    required_path.write_text("workflow_id, max_concurrency, tasks\n", encoding="utf-8")
    context = {
        "issue_id": "ISSUE-8",
        "role": "coder",
        "profile_traits": {
            "intent": "write_artifact",
            "artifact_contract_required": True,
            "runtime_verifier_allowed": False,
        },
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["agent_output/requirements.txt"],
        "required_write_paths": ["agent_output/design.txt"],
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Read Path Contract:" not in rendered
    assert "Preloaded Read Context:" in rendered
    assert "workflow_id, max_concurrency, tasks" in rendered
    assert "Empty or placeholder content for required write_file paths is invalid." in rendered
    assert "prefer single-quoted literals" in rendered
