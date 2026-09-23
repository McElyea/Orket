"""Layer: integration. Opening diagnostic for MessageBuilder input capture.

This ignored module uses real MessageBuilder file reads. It does not define path
authorization or confinement policy and is not packet-2 or v0.6.99 acceptance.
"""

import asyncio
import string
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import prepare_message_fixture
from tests.integration.test_async_file_native_lifetime import hold_native_open

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATHS = ("agent_output/first.txt", "agent_output/second.txt")
_ENTRY_TOOLS = ["read_file", "add_issue_comment", "update_issue_status"]


def _issue() -> IssueConfig:
    return IssueConfig(
        id="ISSUE-INPUT",
        name="Entry issue name",
        seat="reviewer",
        status="in_progress",
        description="Entry issue description",
        requirements="Entry issue requirement",
    )


def _role() -> RoleConfig:
    return RoleConfig(
        id="reviewer",
        name="reviewer",
        description="Entry role description",
        prompt=(
            "Entry role prompt\n\n"
            "PROJECT CONTEXT (PAST DECISIONS):\n"
            "entry-role-project-context"
        ),
        tools=list(_ENTRY_TOOLS),
    )


def _context(prompt_metadata: dict, prompt_layers: dict) -> tuple[dict, dict, list, list]:
    dependency = {
        "dependency_count": 1,
        "depends_on": ["ENTRY-DEP"],
        "unresolved_dependencies": ["ENTRY-WAIT"],
    }
    required_tools = list(_ENTRY_TOOLS)
    history = [{"role": "reviewer", "content": "entry-history-content"}]
    context = {
        "issue_id": "ISSUE-INPUT",
        "role": "reviewer",
        "dependency_context": dependency,
        "required_action_tools": required_tools,
        "required_statuses": ["code_review"],
        "required_read_paths": list(_READ_PATHS),
        "required_write_paths": [],
        "required_comment_min_length": 80,
        "history": history,
        "prompt_metadata": prompt_metadata,
        "prompt_layers": prompt_layers,
    }
    return context, dependency, required_tools, history


async def _write_bytes(path: Path, content: bytes) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, content)


async def _scenario(tmp_path: Path):
    original_workspace = tmp_path / "original-workspace"
    changed_workspace = tmp_path / "changed-workspace"
    expected_bytes: dict[Path, bytes] = {}
    for workspace, label in (
        (original_workspace, "entry"),
        (changed_workspace, "changed"),
    ):
        for index, rel_path in enumerate(_READ_PATHS, 1):
            target = workspace / rel_path
            content = f"{label}-file-{index}-content\n".encode()
            await _write_bytes(target, content)
            expected_bytes[target] = content
    prompt_metadata = {"fixture_identity": "entry-metadata"}
    prompt_layers = {"fixture_identity": "entry-layers"}
    context, dependency, required_tools, history = _context(prompt_metadata, prompt_layers)
    return SimpleNamespace(
        original_workspace=original_workspace,
        changed_workspace=changed_workspace,
        expected_bytes=expected_bytes,
        builder=MessageBuilder(original_workspace),
        issue=_issue(),
        role=_role(),
        context=context,
        dependency=dependency,
        required_tools=required_tools,
        history=history,
        prompt_metadata=prompt_metadata,
        prompt_layers=prompt_layers,
        replacement_metadata=None,
        replacement_layers=None,
    )


def _mutate_input(field: str, scenario) -> None:
    if field == "workspace":
        scenario.builder.workspace = scenario.changed_workspace
    elif field == "issue":
        scenario.issue.name = "Changed issue name"
        scenario.issue.description = "Changed issue description"
        scenario.issue.requirements = "Changed issue requirement"
    elif field == "role":
        scenario.role.name = "changed-role"
        scenario.role.prompt = "Changed role prompt"
        scenario.role.tools[:] = ["changed_tool"]
    elif field == "context":
        scenario.dependency["depends_on"][0] = "MUTATED-IN-PLACE-DEP"
        scenario.required_tools[:] = ["mutated_in_place_tool"]
        scenario.history[0]["content"] = "mutated-in-place-history"
        scenario.context["role"] = "replacement-context-role"
        scenario.context["dependency_context"] = {
            "dependency_count": 9,
            "depends_on": ["REPLACEMENT-DEP"],
        }
        scenario.context["required_action_tools"] = ["replacement_context_tool"]
        scenario.context["required_statuses"] = ["blocked"]
        scenario.context["required_read_paths"] = ["agent_output/replacement-read.txt"]
        scenario.context["history"] = [
            {"role": "changed-role", "content": "replacement-history"}
        ]
        scenario.replacement_metadata = {"fixture_identity": "replacement-metadata"}
        scenario.replacement_layers = {"fixture_identity": "replacement-layers"}
        scenario.context["prompt_metadata"] = scenario.replacement_metadata
        scenario.context["prompt_layers"] = scenario.replacement_layers


def _assert_entry_messages(messages: list[dict[str, str]]) -> None:
    assert [message["role"] for message in messages] == ["system", "user"]
    rendered = "\n".join(message["content"] for message in messages)
    for token in (
        "Issue ISSUE-INPUT: Entry issue name",
        "Description: Entry issue description",
        "Requirements: Entry issue requirement",
        "Project Context:\nentry-role-project-context",
        "- role: reviewer",
        "- required tools: read_file, add_issue_comment, update_issue_status",
        "- allowed statuses: code_review",
        "- required read paths: agent_output/first.txt, agent_output/second.txt",
        "- available tools: read_file, add_issue_comment, update_issue_status",
        "- depends_on: ENTRY-DEP",
        "- unresolved_dependencies: ENTRY-WAIT",
        "entry-history-content",
        "entry-file-1-content",
        "entry-file-2-content",
    ):
        assert token in rendered
    for token in (
        "Changed issue",
        "Changed role",
        "changed-role",
        "changed_tool",
        "changed-file",
        "MUTATED-IN-PLACE",
        "mutated_in_place",
        "replacement-context",
        "REPLACEMENT-DEP",
        "replacement-read",
        "replacement-history",
    ):
        assert token not in rendered


def _assert_compaction_outputs(scenario, *, context_replaced: bool) -> None:
    metadata = scenario.prompt_metadata
    layers = scenario.prompt_layers
    assert metadata["fixture_identity"] == "entry-metadata"
    assert metadata["prompt_packet_compacted"] is True
    assert metadata["prompt_packet_version"] == "compact_turn_packet_v1"
    checksum = metadata["prompt_checksum"]
    assert len(checksum) == 16 and all(character in string.hexdigits for character in checksum)
    packet = layers["packet_compaction"]
    assert packet["enabled"] is True
    assert packet["version"] == "compact_turn_packet_v1"
    assert packet["source_message_count"] > packet["compacted_message_count"] == 2
    if context_replaced:
        assert scenario.context["prompt_metadata"] is scenario.replacement_metadata
        assert scenario.context["prompt_layers"] is scenario.replacement_layers
        assert scenario.replacement_metadata == {"fixture_identity": "replacement-metadata"}
        assert scenario.replacement_layers == {"fixture_identity": "replacement-layers"}
    else:
        assert scenario.context["prompt_metadata"] is metadata
        assert scenario.context["prompt_layers"] is layers


async def _assert_physical_bytes(expected_bytes: dict[Path, bytes]) -> None:
    for path, expected in expected_bytes.items():
        assert await asyncio.to_thread(path.read_bytes) == expected


async def _settle(task, state, timer, expected_bytes: dict[Path, bytes]) -> None:
    errors: list[BaseException] = []
    state.release.set()
    timer.cancel()
    for operation in (
        asyncio.to_thread(timer.join, 5),
        asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5),
    ):
        try:
            await operation
        except BaseException as error:
            errors.append(error)
    if state.entered.is_set():
        try:
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            errors.append(error)
    for stream in state.streams:
        try:
            await asyncio.to_thread(stream.close)
        except BaseException as error:
            errors.append(error)
    try:
        assert not timer.is_alive()
        await _assert_physical_bytes(expected_bytes)
    except BaseException as error:
        errors.append(error)
    if errors:
        first, *rest = errors
        for error in rest:
            first.add_note(f"Additional cleanup failure: {error!r}")
        raise first


@pytest.mark.parametrize("field", ["workspace", "issue", "role", "context"])
@pytest.mark.parametrize("mutate", [False, True], ids=["healthy", "caller-mutation"])
async def test_message_builder_captures_each_input_before_first_native_read(
    tmp_path: Path, monkeypatch, record_property, field: str, mutate: bool
) -> None:
    scenario = await _scenario(tmp_path)
    target = scenario.original_workspace / _READ_PATHS[0]
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[]
    )
    hold_native_open(monkeypatch, target, state, failure=False)
    timer = threading.Timer(0.8, state.release.set)
    timer.start()
    task = asyncio.create_task(
        prepare_message_fixture(scenario.builder,
            issue=scenario.issue,
            role=scenario.role,
            context=scenario.context,
        )
    )
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        if mutate:
            _mutate_input(field, scenario)
        state.release.set()
        messages = await asyncio.wait_for(task, 5)
        _assert_entry_messages(messages)
        _assert_compaction_outputs(scenario, context_replaced=mutate and field == "context")
        assert state.finished.is_set() and state.streams
        assert all(stream.closed for stream in state.streams)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle(task, state, timer, scenario.expected_bytes)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Fixture cleanup also failed: {cleanup_error!r}")
