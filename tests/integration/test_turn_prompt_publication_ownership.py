"""Layer: integration. Prompt inputs and ordered writes retain one owner."""
from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.middleware import MiddlewareOutcome, TurnLifecycleInterceptors
from orket.application.services.tool_gate_service import ToolGate
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_prompt_publication import prepare_prompt_and_write_artifacts
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import artifact_destination, artifact_test_utc_now

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _destination(workspace: Path):
    return artifact_destination(
        TurnArtifactWriter(workspace), session_id="prompt-session", issue_id="PROMPT-ISSUE",
        role_name="developer", role_id="DEV", turn_index=1,
    )


def _hold_write(monkeypatch, target: Path, *, fault: bool = False):
    original = Path.write_text
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
        threads=[], calls=[], fault="",
    )

    def held(path, *args, **kwargs):
        if path != target:
            return original(path, *args, **kwargs)
        state.calls.append(str(path))
        state.threads.append(threading.get_ident())
        state.entered.set()
        try:
            assert state.release.wait(5), "Native prompt write was not released"
            if fault:
                path.mkdir()
            return original(path, *args, **kwargs)
        except OSError as error:
            state.fault = type(error).__name__
            raise
        finally:
            state.finished.set()

    monkeypatch.setattr(Path, "write_text", held)
    return state


async def _settle(task, state, primary_error: BaseException | None) -> None:
    state.release.set()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
    except BaseException as error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Prompt publication cleanup also failed: {error!r}")


async def _unexpected_failure(*_args, **_kwargs) -> None:
    pytest.fail("healthy prompt publication emitted failure")


async def _publish_prompt(destination, messages, context, deadline):
    async with asyncio.timeout(5), deadline:
        return await prepare_prompt_and_write_artifacts(
            destination=destination, model_client=object(), context=context, messages=messages,
            turn_trace_id="prompt-trace", emit_failure=_unexpected_failure,
            turn_result_failed=lambda *_args, **_kwargs: pytest.fail("unexpected failed result"),
        )


async def _interrupt(task, deadline, stop: str) -> None:
    if stop == "cancel":
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
    elif stop == "timeout":
        deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
    if stop != "none":
        await asyncio.sleep(0.03)


async def _observe_publication_result(
    task, *, fault: bool, stop: str, destination, messages,
) -> None:
    if fault:
        with pytest.raises((PermissionError, IsADirectoryError)):
            await asyncio.wait_for(asyncio.shield(task), 5)
    elif stop == "none":
        captured_messages, prompt_hash, early = await asyncio.wait_for(asyncio.shield(task), 5)
        assert captured_messages == messages and early is None
        assert prompt_hash == destination.writer.message_hash(messages)
    else:
        with pytest.raises(asyncio.CancelledError if stop == "cancel" else TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 5)


async def _assert_prompt_files(
    *, messages_path, layers_path, messages, layers, document: str, fault: bool, stop: str,
) -> tuple[bool, bool]:
    messages_file = await asyncio.to_thread(messages_path.is_file)
    layers_file = await asyncio.to_thread(layers_path.is_file)
    if messages_file:
        assert json.loads(await asyncio.to_thread(messages_path.read_text, encoding="utf-8")) == messages
    if layers_file:
        assert json.loads(await asyncio.to_thread(layers_path.read_text, encoding="utf-8")) == layers
    assert messages_file is (document == "layers" or (not fault))
    expected_layers = (document == "layers" and not fault) or (
        document == "messages" and not fault and stop == "none"
    )
    assert layers_file is expected_layers
    return messages_file, layers_file


@pytest.mark.parametrize("document", ["messages", "layers"])
@pytest.mark.parametrize("fault", [False, True], ids=["write", "late-directory-fault"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_prompt_documents_retain_admitted_native_write(
    tmp_path, monkeypatch, record_property, document, fault, stop,
) -> None:
    """Layer: integration. Each real prompt write drains and gates the next."""
    destination = _destination(tmp_path)
    messages_path = destination.file_path("messages.json")
    layers_path = destination.file_path("prompt_layers.json")
    target = messages_path if document == "messages" else layers_path
    state = _hold_write(monkeypatch, target, fault=fault)
    messages = [{"role": "user", "content": "captured prompt"}]
    layers = {"fixture": {"value": "captured layer"}}
    deadline = asyncio.timeout(None)
    task = asyncio.create_task(_publish_prompt(
        destination, messages, {"prompt_layers": layers}, deadline,
    ))
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
        await _interrupt(task, deadline, stop)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        await _observe_publication_result(
            task, fault=fault, stop=stop, destination=destination, messages=messages,
        )
        assert state.finished.is_set()
        messages_file, layers_file = await _assert_prompt_files(
            messages_path=messages_path, layers_path=layers_path, messages=messages, layers=layers,
            document=document, fault=fault, stop=stop,
        )
        record_property("prompt_write_observation", json.dumps({
            "document": document, "fault": fault, "stop": stop,
            "native_error": state.fault, "messages_file": messages_file,
            "layers_file": layers_file,
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, primary_error)


class _RetainedPromptMiddleware:
    def __init__(self) -> None:
        self.messages: list[dict[str, str]] | None = None

    def before_prompt(self, messages, **_kwargs):
        self.messages = [*messages, {"role": "user", "content": "retained prompt A"}]
        return MiddlewareOutcome(replacement=self.messages)


class _CorrectiveModel:
    def __init__(self) -> None:
        self.messages: list[list[dict[str, str]]] = []

    async def complete(self, messages):
        self.messages.append([dict(row) for row in messages])
        path = "agent_output/wrong.txt" if len(self.messages) == 1 else "agent_output/final.txt"
        return {"content": json.dumps({"tool": "write_file", "args": {
            "path": path, "content": "ok",
        }}), "raw": {"response_id": len(self.messages)}}


class _FileToolbox:
    def __init__(self, workspace: Path) -> None:
        self.files = AsyncFileTools(workspace)

    async def execute(self, tool_name, args, context=None):
        await self.files.write_file(str(args["path"]), str(args.get("content") or ""))
        return {"ok": True, "tool": tool_name, "touched_paths": [str(args["path"])]}


async def test_composed_turn_shares_captured_prompt_with_model_and_corrective_base(
    tmp_path, monkeypatch, record_property,
) -> None:
    """Layer: integration. Artifact, model and corrective inputs share entry A."""
    middleware = _RetainedPromptMiddleware()
    executor = TurnExecutor(
        StateMachine(), ToolGate(organization=None, workspace_root=tmp_path), workspace=tmp_path,
        middleware=TurnLifecycleInterceptors([middleware]), utc_now=artifact_test_utc_now,
    )
    issue = IssueConfig(id="PROMPT-ISSUE", summary="Prompt capture", status=CardStatus.IN_PROGRESS)
    role = RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])
    context = {
        "session_id": "prompt-session", "issue_id": issue.id, "role": "developer",
        "roles": ["developer"], "current_status": "in_progress", "turn_index": 1,
        "selected_model": "controlled", "history": [], "compact_turn_packet_enabled": False,
        "required_action_tools": ["write_file"],
        "required_write_paths": ["agent_output/final.txt"],
        "prompt_layers": {"fixture": "captured layer A"},
    }
    destination = artifact_destination(
        executor.artifact_writer, session_id="prompt-session", issue_id=issue.id,
        role_name="developer", role_id="DEV", turn_index=1,
    )
    messages_path = destination.file_path("messages.json")
    state = _hold_write(monkeypatch, messages_path)
    model = _CorrectiveModel()
    toolbox = _FileToolbox(tmp_path)
    task = asyncio.create_task(executor.execute_turn(
        issue, role, model, toolbox, context, system_prompt="SYSTEM",
    ))
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "composed.sqlite3", record_property)
        assert middleware.messages is not None
        middleware.messages[-1]["content"] = "retained prompt B"
        middleware.messages.append({"role": "user", "content": "late prompt B"})
        state.release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 15)
        assert state.finished.is_set()
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
        physical = json.loads(await asyncio.to_thread(messages_path.read_text, encoding="utf-8"))
        checkpoint = json.loads(await asyncio.to_thread(
            destination.file_path("checkpoint.json").read_text, encoding="utf-8"))
        layers = json.loads(await asyncio.to_thread(
            destination.file_path("prompt_layers.json").read_text, encoding="utf-8"))
        assert result.success and len(model.messages) == 2
        assert model.messages[0] == physical
        assert model.messages[1][:-1] == physical
        assert model.messages[1][-1]["content"].startswith("Corrective instruction:")
        assert "retained prompt A" in json.dumps(physical)
        assert "retained prompt B" not in json.dumps(model.messages)
        assert "late prompt B" not in json.dumps(model.messages)
        assert checkpoint["prompt_hash"] == executor.artifact_writer.message_hash(physical)
        assert layers == {"fixture": "captured layer A"}
        assert await toolbox.files.read_file("agent_output/final.txt") == "ok"
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, primary_error)
