"""Integration: MessageBuilder captures used prompt inputs without copying runtime resources."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _OpaqueResource:
    def __init__(self) -> None:
        self.touches: list[str] = []

    def _touched(self, operation: str):
        self.touches.append(operation)
        raise AssertionError(f"unused opaque resource was {operation}")

    def __copy__(self):
        return self._touched("copied")

    def __deepcopy__(self, memo):
        return self._touched("deep-copied")

    def __bool__(self):
        return self._touched("coerced to bool")

    def __iter__(self):
        return self._touched("iterated")

    def __str__(self):
        return self._touched("converted to text")


def _hold_resolve(monkeypatch: pytest.MonkeyPatch, target: Path) -> SimpleNamespace:
    release = threading.Event()
    timer = threading.Timer(2.0, release.set)
    timer.daemon = True
    state = SimpleNamespace(
        entered=threading.Event(), release=release, finished=threading.Event(),
        timer=timer, timer_started=threading.Event(),
    )
    original = Path.resolve

    def held(path: Path, *args, **kwargs):
        if path != target or state.entered.is_set():
            return original(path, *args, **kwargs)
        state.entered.set()
        state.timer.start()
        state.timer_started.set()
        try:
            assert state.release.wait(5), "held path resolution was not released"
            return original(path, *args, **kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "resolve", held)
    return state


def _inputs(opaque: _OpaqueResource, *, compact: bool) -> tuple[IssueConfig, RoleConfig, dict[str, Any]]:
    issue = IssueConfig(
        id="CAPTURE-1",
        summary="Original issue",
        status="in_progress",
        description="Original description",
        requirements="Original requirement",
        note="Original note",
        references=["original-reference"],
    )
    role = RoleConfig(
        id="original-role",
        summary="original_role",
        description="Original role description",
        prompt="SYSTEM ORIGINAL",
        tools=["read_file", "write_file"],
    )
    issue.params["unused_resource"] = opaque
    role.policy["unused_resource"] = opaque
    role.capabilities["unused_resource"] = opaque
    context: dict[str, Any] = {
        "session_id": "original-session",
        "turn_index": 7,
        "issue_id": "CAPTURE-1",
        "role": "original_role",
        "current_status": "in_progress",
        "required_action_tools": ["read_file", "write_file", "add_issue_comment"],
        "required_statuses": ["code_review"],
        "required_read_paths": ["inputs/original.txt"],
        "required_write_paths": ["agent_output/original.py"],
        "required_comment_contains": ["Original finding"],
        "dependency_context": {"dependency_count": 1, "depends_on": ["ORIGINAL-DEP"]},
        "profile_traits": {"intent": "write_artifact", "runtime_verifier_allowed": True},
        "artifact_contract": {
            "kind": "app",
            "primary_output": "agent_output/original.py",
            "semantic_checks": [{"path": "agent_output/original.py", "must_contain": ["ORIGINAL_TOKEN"]}],
        },
        "scenario_truth": {"scenario_id": "original-scenario"},
        "runtime_verifier_contract": {"commands": [["python", "agent_output/original.py"]]},
        "architecture_decision_required": True,
        "architecture_allowed_patterns": ["original-pattern"],
        "history": [{"role": "original-actor", "content": "Original history"}],
        "prompt_metadata": {"prompt_id": "original.prompt"},
        "prompt_layers": {"role_base": {"name": "original_role"}},
        "compact_turn_packet_enabled": compact,
        "execution_resource": opaque,
    }
    return issue, role, context


def _mutate_used_inputs(
    builder: MessageBuilder,
    issue: IssueConfig,
    role: RoleConfig,
    context: dict[str, Any],
    changed_workspace: Path,
) -> None:
    builder.workspace = changed_workspace
    issue.id = "MUTATED-ISSUE"
    issue.name = "MUTATED issue"
    issue.description = "MUTATED description"
    issue.requirements = "MUTATED requirement"
    issue.note = "MUTATED note"
    issue.references.append("MUTATED reference")
    role.name = "MUTATED_role"
    role.prompt = "SYSTEM MUTATED"
    role.description = "MUTATED role description"
    role.tools.append("MUTATED_tool")
    context["role"] = "MUTATED_role"
    context["current_status"] = "MUTATED_status"
    context["required_action_tools"].append("MUTATED_tool")
    context["required_statuses"].append("MUTATED_status")
    context["required_read_paths"][:] = ["inputs/mutated.txt"]
    context["required_write_paths"].append("MUTATED-output")
    context["required_comment_contains"].append("MUTATED-comment")
    context["dependency_context"]["depends_on"].append("MUTATED-DEP")
    context["artifact_contract"]["semantic_checks"][0]["must_contain"].append("MUTATED_TOKEN")
    context["scenario_truth"]["scenario_id"] = "MUTATED-scenario"
    context["runtime_verifier_contract"]["commands"][0].append("MUTATED-arg")
    context["architecture_allowed_patterns"].append("MUTATED-pattern")
    context["history"][0]["content"] = "MUTATED history"
    context["prompt_metadata"]["prompt_id"] = "MUTATED.prompt"


async def _settle_started_task(task: asyncio.Task, state: SimpleNamespace) -> str | None:
    problems: list[str] = []
    state.release.set()
    state.timer.cancel()
    if state.timer_started.is_set():
        try:
            await asyncio.to_thread(state.timer.join, 5)
            if state.timer.is_alive():
                problems.append("metadata auto-release timer did not join")
        except BaseException as exc:
            problems.append(f"metadata timer cleanup failed: {type(exc).__name__}")
    try:
        if not task.done():
            await asyncio.wait_for(asyncio.shield(task), 5)
    except TimeoutError:
        task.cancel()
        problems.append("message preparation did not settle after metadata release")
    except BaseException:
        pass
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    except TimeoutError:
        problems.append("message preparation cancellation did not settle")
    except BaseException as exc:
        problems.append(f"message preparation cleanup failed: {type(exc).__name__}")
    if state.entered.is_set():
        try:
            if not await asyncio.to_thread(state.finished.wait, 5):
                problems.append("held metadata operation did not finish")
        except BaseException as exc:
            problems.append(f"metadata completion wait failed: {type(exc).__name__}")
    return "; ".join(problems) or None


async def _run_during_metadata_hold(
    preparation: Coroutine[Any, Any, list[dict[str, str]]],
    state: SimpleNamespace,
    mutate: Callable[[], None],
) -> list[dict[str, str]]:
    task: asyncio.Task[list[dict[str, str]]] | None = None
    primary_failure: BaseException | None = None
    try:
        task = asyncio.create_task(preparation)
        entered = await asyncio.to_thread(state.entered.wait, 5)
        if not entered and task.done():
            await task
        assert entered, "message preparation never reached held native metadata"
        assert not state.finished.is_set(), "metadata hold auto-released before mutation"
        assert not task.done(), "metadata observation blocked the event loop through native completion"
        mutate()
        state.release.set()
        return await asyncio.wait_for(asyncio.shield(task), 5)
    except BaseException as exc:
        primary_failure = exc
        raise
    finally:
        if task is None:
            preparation.close()
        else:
            cleanup_problem = await _settle_started_task(task, state)
            if cleanup_problem is not None and primary_failure is None:
                raise AssertionError(cleanup_problem)


@pytest.mark.parametrize("compact", [False, True])
async def test_used_prompt_values_are_captured_while_opaque_resources_remain_untouched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compact: bool,
) -> None:
    workspace, changed = tmp_path / "workspace", tmp_path / "changed"
    original_file, changed_file = workspace / "inputs/original.txt", changed / "inputs/original.txt"
    await asyncio.to_thread(original_file.parent.mkdir, parents=True)
    await asyncio.to_thread(changed_file.parent.mkdir, parents=True)
    await asyncio.to_thread(original_file.write_text, "ORIGINAL FILE CONTENT", encoding="utf-8")
    await asyncio.to_thread(changed_file.write_text, "MUTATED FILE CONTENT", encoding="utf-8")
    original_bytes = await asyncio.to_thread(original_file.read_bytes)
    changed_bytes = await asyncio.to_thread(changed_file.read_bytes)
    opaque = _OpaqueResource()
    issue, role, context = _inputs(opaque, compact=compact)
    builder = MessageBuilder(workspace)
    state = _hold_resolve(monkeypatch, original_file)

    messages = await _run_during_metadata_hold(
        builder.prepare_messages(issue=issue, role=role, context=context),
        state,
        lambda: _mutate_used_inputs(builder, issue, role, context, changed),
    )
    rendered = "\n\n".join(message["content"] for message in messages)

    for expected in (
        "CAPTURE-1", "Original issue", "Original description", "Original requirement", "Original note",
        "original-reference", "original_role", "ORIGINAL-DEP", "ORIGINAL_TOKEN", "original-scenario",
        "python agent_output/original.py", "original-pattern", "Original history", "ORIGINAL FILE CONTENT",
        "agent_output/original.py",
    ):
        assert expected in rendered
    assert "MUTATED" not in rendered
    if compact:
        assert "- available tools: read_file, write_file" in rendered
    else:
        assert "SYSTEM ORIGINAL" in rendered
        assert '"prompt_id": "original.prompt"' in rendered
    assert opaque.touches == []
    assert await asyncio.to_thread(original_file.read_bytes) == original_bytes
    assert await asyncio.to_thread(changed_file.read_bytes) == changed_bytes


@pytest.mark.parametrize("aliased", [False, True])
async def test_compaction_publishes_only_to_original_output_sinks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    aliased: bool,
) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "inputs/original.txt"
    await asyncio.to_thread(target.parent.mkdir, parents=True)
    await asyncio.to_thread(target.write_text, "ORIGINAL FILE CONTENT", encoding="utf-8")
    target_bytes = await asyncio.to_thread(target.read_bytes)
    issue, role, context = _inputs(_OpaqueResource(), compact=True)
    if aliased:
        shared = {**context["prompt_metadata"], **context["prompt_layers"]}
        context["prompt_metadata"] = shared
        context["prompt_layers"] = shared
    original_metadata = context["prompt_metadata"]
    original_layers = context["prompt_layers"]
    builder = MessageBuilder(workspace)
    state = _hold_resolve(monkeypatch, target)

    replacement_metadata = {"replacement": "metadata"}
    replacement_layers = {"replacement": "layers"}

    def replace_output_slots() -> None:
        context["prompt_metadata"] = replacement_metadata
        context["prompt_layers"] = replacement_layers

    messages = await _run_during_metadata_hold(
        builder.prepare_messages(issue=issue, role=role, context=context), state, replace_output_slots,
    )

    assert len(messages) == 2
    assert original_metadata["prompt_packet_version"] == "compact_turn_packet_v1"
    assert original_metadata["prompt_packet_compacted"] is True
    assert isinstance(original_metadata["prompt_checksum"], str)
    packet = original_layers["packet_compaction"]
    assert packet["enabled"] is True
    assert packet["version"] == "compact_turn_packet_v1"
    assert packet["source_message_count"] > packet["compacted_message_count"] == 2
    assert replacement_metadata == {"replacement": "metadata"}
    assert replacement_layers == {"replacement": "layers"}
    assert await asyncio.to_thread(target.read_bytes) == target_bytes
