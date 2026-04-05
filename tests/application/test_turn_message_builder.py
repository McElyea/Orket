from __future__ import annotations

from pathlib import Path

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", name="Demo", seat="coder", status="in_progress")


def _role() -> RoleConfig:
    return RoleConfig(id="coder", name="coder", description="Writes code", prompt="You are coder", tools=["write_file"])


async def test_message_builder_includes_execution_context(tmp_path: Path) -> None:
    """Layer: contract. Verifies builder emits one compact turn packet instead of stacked user contract blocks."""
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
    assert [message["role"] for message in messages] == ["system", "user"]
    assert "MODE: compact governed tool turn" in messages[0]["content"]
    rendered = messages[1]["content"]
    assert "TURN PACKET:" in rendered
    assert "- required tools: write_file" in rendered
    assert "- allowed statuses: done" in rendered
    assert "- required write paths: agent_output/main.py" in rendered
    assert "Execution Context JSON" not in rendered
    assert "Write Path Contract:" not in rendered


async def test_message_builder_serializes_history_as_user_block(tmp_path: Path) -> None:
    """Layer: contract. Verifies prior transcript history is folded into the compact turn packet."""
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
    rendered = messages[1]["content"]
    assert "Prior Transcript JSON:" in rendered
    assert '"actor": "coder"' in rendered
    assert '"actor": "integrity_guard"' in rendered


async def test_message_builder_adds_protocol_response_contract_when_governed(tmp_path: Path) -> None:
    """Layer: contract. Verifies governed turns keep the response envelope inside the compact packet."""
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
    assert [message["role"] for message in messages] == ["system", "user"]
    assert 'Response envelope: {"content":"","tool_calls":[...]}' in messages[0]["content"]
    assert '- response shape: {"content":"","tool_calls":[...]}' in messages[1]["content"]
    assert "Protocol Response Contract:" not in messages[1]["content"]


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

    assert "Review Comment Rules:" in rendered
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

    assert "Runtime Verification:" in rendered
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

    assert "Runtime Verification:" in rendered
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

    assert "Runtime Verification:" in rendered
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

    assert "Artifact Checks:" in rendered
    assert "checked as an exact substring" in rendered
    assert "Path: agent_output/main.py" in rendered
    assert "Purpose: script entrypoint imports" in rendered
    assert "Must contain: from challenge_runtime" in rendered
    assert "Must not contain: from .challenge_runtime" in rendered


async def test_message_builder_includes_artifact_exact_shape_hints_for_simulator_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5C",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/simulator.py",
            "required_write_paths": ["agent_output/challenge_runtime/simulator.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/simulator.py",
                    "label": "deterministic simulator",
                    "must_contain": [
                        "for layer in layers",
                        "ready_tasks = self.get_ready_tasks(layer)",
                        "batch = ready_tasks[:self.workflow['max_concurrency']]",
                        "self.run_task(task)",
                        "task['retries'] + 1",
                    ],
                    "must_not_contain": [],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "Keep the planner loop in this exact layer-driven form" in rendered
    assert "Do not replace layers with self.layers" in rendered


async def test_message_builder_includes_artifact_exact_shape_hints_for_validator_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5D",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/tests/test_validator_and_planner.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/tests/test_validator_and_planner.py",
            "required_write_paths": ["agent_output/tests/test_validator_and_planner.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/tests/test_validator_and_planner.py",
                    "label": "validator and planner tests use real fixture paths",
                    "must_contain": [
                        "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_cycle.json'",
                        "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_valid.json'",
                        "write_text(json.dumps(",
                    ],
                    "must_not_contain": ["tmp_path / 'workflow_valid.json'"],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "workflow_cycle_path = Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_cycle.json'" in rendered
    assert "Never create or validate tmp_path / 'workflow_valid.json'." in rendered


async def test_message_builder_includes_artifact_import_hints_for_loader_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5E",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/loader.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/loader.py",
            "required_write_paths": ["agent_output/challenge_runtime/loader.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/loader.py",
                    "label": "loader normalizes workflow json into mappings",
                    "must_contain": [
                        "from .models import TaskSpec, WorkflowSpec",
                        "json.load(",
                        "def load_workflow(path: str) -> WorkflowSpec:",
                        "def normalize_task(raw_task) -> TaskSpec:",
                        "'tasks': [normalize_task(task) for task in data['tasks']]",
                    ],
                    "must_not_contain": [
                        "agent_output.challenge_runtime",
                        "WorkflowSpec(**data)",
                        "TaskSpec(**raw_task)",
                    ],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "return {'workflow_id': data['workflow_id'], 'max_concurrency': data['max_concurrency'], 'tasks': [normalize_task(task) for task in data['tasks']]}" in rendered
    assert "Do not call WorkflowSpec(**data) or TaskSpec(**raw_task)" in rendered


async def test_message_builder_includes_artifact_shape_hints_for_models_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5E0",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/models.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/models.py",
            "required_write_paths": ["agent_output/challenge_runtime/models.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/models.py",
                    "label": "models define separated typed schema maps",
                    "must_contain": [
                        "from typing import List, TypedDict",
                        "class TaskSpec(TypedDict):",
                        "class WorkflowSpec(TypedDict):",
                        "tasks: List[TaskSpec]",
                    ],
                    "must_not_contain": ["@dataclass"],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "TaskSpec limited to task-level fields only" in rendered
    assert "WorkflowSpec limited to root-level fields only" in rendered


async def test_message_builder_includes_artifact_export_hints_for_package_init_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5E1",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/__init__.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/__init__.py",
            "required_write_paths": ["agent_output/challenge_runtime/__init__.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/__init__.py",
                    "label": "package exports",
                    "must_contain": [
                        "from .models import TaskSpec, WorkflowSpec",
                        "from .loader import load_workflow, normalize_task",
                    ],
                    "must_not_contain": [],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "Do not leave challenge_runtime/__init__.py empty." in rendered
    assert "from .loader import load_workflow, normalize_task" in rendered


async def test_message_builder_includes_artifact_import_hints_for_validator_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5F",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/validator.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/validator.py",
            "required_write_paths": ["agent_output/challenge_runtime/validator.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/validator.py",
                    "label": "validator schema and error codes",
                    "must_contain": [
                        "def validate_workflow(path: str)",
                        "from .loader import load_workflow",
                        "from .models import WorkflowSpec, TaskSpec",
                        "load_workflow(path)",
                    ],
                    "must_not_contain": ["agent_output.challenge_runtime"],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "from .loader import load_workflow" in rendered
    assert "Never import through agent_output.challenge_runtime" in rendered


async def test_message_builder_includes_artifact_order_hints_for_planner_contract(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5G",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/challenge_runtime/planner.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/challenge_runtime/planner.py",
            "required_write_paths": ["agent_output/challenge_runtime/planner.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/challenge_runtime/planner.py",
                    "label": "planner imports and surface",
                    "must_contain": [
                        "task_ids = [task['id'] for task in workflow['tasks']]",
                        "zero_in_degree = [task_id for task_id in task_ids if in_degree[task_id] == 0]",
                        "for task_id in current_layer",
                        "adjacency_list[dep].append(task['id'])",
                        "in_degree[task['id']] += 1",
                    ],
                    "must_not_contain": ["for task_id in task_ids:"],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "Compute zero_in_degree only after that dependency scan" in rendered
    assert "do not place every task in the first layer" in rendered


async def test_message_builder_includes_artifact_shape_hints_for_simulator_resume_tests(tmp_path: Path) -> None:
    builder = MessageBuilder(tmp_path)
    context = {
        "issue_id": "ISSUE-5H",
        "role": "coder",
        "required_action_tools": ["write_file", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [],
        "required_write_paths": ["agent_output/tests/test_simulator_and_resume.py"],
        "artifact_contract": {
            "kind": "artifact",
            "primary_output": "agent_output/tests/test_simulator_and_resume.py",
            "required_write_paths": ["agent_output/tests/test_simulator_and_resume.py"],
            "semantic_checks": [
                {
                    "path": "agent_output/tests/test_simulator_and_resume.py",
                    "label": "simulator tests use admitted proof surface",
                    "must_contain": [
                        "def test_simulator_and_resume(tmp_path):",
                        "from challenge_runtime.simulator import Simulator",
                        "from challenge_runtime.checkpoint import save_checkpoint, load_checkpoint, resume_simulation",
                        "Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_retry.json'",
                        "artifact_root = Path(__file__).resolve().parents[1] / 'challenge_artifacts'",
                        "checkpoint_path = artifact_root / 'retry_checkpoint.json'",
                        "resumed_terminal_state == 'completed'",
                        "resumed_again_terminal_state == 'completed'",
                        "tmp_path / 'workflow_dependency_gating.json'",
                        "write_text(json.dumps(",
                    ],
                    "must_not_contain": [
                        "checkpoint_path = tmp_path /",
                        "tmp_path = Path(__file__).resolve().parents[1] / 'tmp'",
                        "from challenge_runtime.simulator import Simulator, save_checkpoint, load_checkpoint, resume_simulation",
                    ],
                }
            ],
        },
        "history": [],
    }

    messages = await builder.prepare_messages(issue=_issue(), role=_role(), context=context)
    rendered = "\n".join(m["content"] for m in messages)

    assert "Exact Shape Hints:" in rendered
    assert "def test_simulator_and_resume(tmp_path):" in rendered
    assert "from challenge_runtime.checkpoint import save_checkpoint, load_checkpoint, resume_simulation" in rendered
    assert "workflow_retry_path = Path(__file__).resolve().parents[1] / 'challenge_inputs' / 'workflow_retry.json'" in rendered
    assert "resumed_terminal_state = resumed.terminal_state" in rendered
    assert "'id': 'upstream'" in rendered
    assert "'retries': 0" in rendered
    assert "dependency_gating_path = tmp_path / 'workflow_dependency_gating.json'" in rendered
    assert "Do not invent a repo-local tmp directory" in rendered


async def test_message_builder_includes_single_envelope_contract_for_legacy_multi_tool_turns(tmp_path: Path) -> None:
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

    assert "Return exactly one JSON object." in rendered
    assert 'Response envelope: {"content":"","tool_calls":[...]}' in rendered
    assert '- response shape: {"content":"","tool_calls":[...]}' in rendered
    assert "You must include all required tool calls in this same response." in rendered


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
    assert "Runtime Verification:" not in rendered
    assert "Scenario Constraints:" in rendered
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
