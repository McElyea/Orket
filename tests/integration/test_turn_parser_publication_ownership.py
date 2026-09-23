"""Layer: integration. Real parser artifact batch ownership and capture controls."""
from __future__ import annotations

import asyncio
import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.workflows import turn_response_parser as parser_module
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_response_capture import capture_turn_response
from orket.application.workflows.turn_response_parser import ResponseParser
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_NOW = datetime(2026, 9, 23, 18, 30, tzinfo=UTC)


def _destination(workspace: Path) -> TurnArtifactDestination:
    writer = TurnArtifactWriter(workspace)
    return TurnArtifactDestination(
        writer=writer, workspace=workspace, session_id="parser-session", issue_id="PARSER-ISSUE",
        role_name="reviewer", role_id="REVIEWER", turn_index=2,
    )


def _paths(destination: TurnArtifactDestination) -> tuple[Path, Path, Path]:
    return tuple(destination.file_path(name) for name in (
        "tool_parser_diagnostics.json", "parsed_tool_calls.json", "tool_parser_summary.json",
    ))


def _hold_batch(monkeypatch, destination: TurnArtifactDestination, fault_stage: str | None):
    paths = _paths(destination)
    target = destination.output_dir if fault_stage == "mkdir" else paths[1 if fault_stage == "second" else 0]
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event(),
                            threads=[], fault="", calls=[])
    if fault_stage == "mkdir":
        original = Path.mkdir

        def held(path, *args, **kwargs):
            if path != target:
                return original(path, *args, **kwargs)
            state.calls.append(str(path))
            state.threads.append(threading.get_ident())
            state.entered.set()
            try:
                assert state.release.wait(5), "Native parser mkdir was not released"
                original(path.parent, parents=True, exist_ok=True)
                path.write_bytes(b"blocking file\n")
                return original(path, *args, **kwargs)
            except OSError as error:
                state.fault = type(error).__name__
                raise
            finally:
                state.finished.set()

        monkeypatch.setattr(Path, "mkdir", held)
    else:
        original = Path.write_text

        def held(path, *args, **kwargs):
            if path != target:
                return original(path, *args, **kwargs)
            state.calls.append(str(path))
            state.threads.append(threading.get_ident())
            state.entered.set()
            try:
                assert state.release.wait(5), "Native parser write was not released"
                if fault_stage in {"first", "second"}:
                    path.mkdir()
                return original(path, *args, **kwargs)
            except OSError as error:
                state.fault = type(error).__name__
                raise
            finally:
                state.finished.set()

        monkeypatch.setattr(Path, "write_text", held)
    return state, paths


async def _settle(task, state, primary_error: BaseException | None) -> None:
    if not task.done():
        task.cancel()
    state.release.set()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
        if state.entered.is_set():
            assert await asyncio.to_thread(state.finished.wait, 5)
    except BaseException as error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Parser cleanup also failed: {error!r}")


async def _interrupt(stop: str, task, deadline) -> None:
    if stop == "cancel":
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
    elif stop == "timeout":
        deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
    if stop != "none":
        await asyncio.sleep(0.03)


async def _observe_result(task, *, fault_stage: str | None, stop: str, clock_calls) -> None:
    if fault_stage is not None:
        with pytest.raises(OSError):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert clock_calls == []
    elif stop == "none":
        turn = await asyncio.wait_for(asyncio.shield(task), 5)
        assert turn.timestamp == _NOW
    else:
        with pytest.raises(asyncio.CancelledError if stop == "cancel" else TimeoutError):
            await asyncio.wait_for(asyncio.shield(task), 5)


async def _assert_artifacts(paths, *, fault_stage: str | None, clock_calls) -> list[bool]:
    if fault_stage is None:
        assert len(clock_calls) == 1 and clock_calls[0][1] == (True, True, True)
        assert all(await asyncio.gather(*(asyncio.to_thread(path.is_file) for path in paths)))
    elif fault_stage == "mkdir":
        assert not any(await asyncio.gather(*(asyncio.to_thread(path.exists) for path in paths)))
    elif fault_stage == "first":
        assert await asyncio.to_thread(paths[0].is_dir)
        assert not await asyncio.to_thread(paths[1].exists)
    else:
        assert await asyncio.to_thread(paths[0].is_file)
        assert await asyncio.to_thread(paths[1].is_dir)
        assert not await asyncio.to_thread(paths[2].exists)
    return list(await asyncio.gather(*(asyncio.to_thread(path.exists) for path in paths)))


@pytest.mark.parametrize("fault_stage", [None, "mkdir", "first", "second"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_parser_batch_retains_admitted_native_work(
    tmp_path, monkeypatch, record_property, fault_stage, stop,
) -> None:
    """Layer: integration. The real three-file parser batch drains."""
    destination = _destination(tmp_path)
    state, paths = _hold_batch(monkeypatch, destination, fault_stage)
    clock_calls: list[tuple[int, tuple[bool, ...]]] = []

    def utc_now() -> datetime:
        clock_calls.append((threading.get_ident(), tuple(path.exists() for path in paths)))
        return _NOW

    parser = ResponseParser(utc_now=utc_now)
    response = capture_turn_response({
        "content": '{"tool":"read_file","args":{"path":"agent_output/a.txt"}}',
        "raw": {"total_tokens": 7},
    })
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await parser.parse_response(response=response, destination=destination, context={})

    task = asyncio.create_task(operation())
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert state.threads == [state.threads[0]] and state.threads[0] != threading.get_ident()
        await _interrupt(stop, task, deadline)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        await _observe_result(task, fault_stage=fault_stage, stop=stop, clock_calls=clock_calls)
        assert state.finished.is_set()
        observed_paths = await _assert_artifacts(paths, fault_stage=fault_stage, clock_calls=clock_calls)
        record_property("parser_batch_observation", json.dumps({
            "fault_stage": fault_stage, "stop": stop, "native_error": state.fault,
            "clock_calls": len(clock_calls), "paths": observed_paths,
        }, sort_keys=True))
    except BaseException as error:
        primary_error = error
        raise
    finally:
        await _settle(task, state, primary_error)


async def test_parser_uses_captured_response_and_policy_during_held_operation(
    tmp_path, monkeypatch, record_property,
) -> None:
    """Layer: integration. Held parsing uses entry response and policy."""
    destination = _destination(tmp_path)
    paths = _paths(destination)
    state = SimpleNamespace(entered=threading.Event(), release=threading.Event(), finished=threading.Event())
    operation = parser_module.parse_and_publish_response

    def held_operation(**kwargs):
        state.entered.set()
        try:
            assert state.release.wait(5), "Parser capture operation was not released"
            return operation(**kwargs)
        finally:
            state.finished.set()

    monkeypatch.setattr(parser_module, "parse_and_publish_response", held_operation)
    raw_call = {"function": {"name": "read_file", "arguments": '{"args":{"path":"a.txt"}}'}}
    original = SimpleNamespace(content="", raw={
        "tool_calls": [raw_call], "total_tokens": 9,
        "extension": {"borrowed": True},
    })
    captured = capture_turn_response(original)
    borrowed = original.raw["extension"]
    context = {"required_action_tools": ["read_file"], "protocol_governed_enabled": False}
    parser = ResponseParser(utc_now=lambda: _NOW)
    task = asyncio.create_task(parser.parse_response(
        response=captured, destination=destination, context=context,
    ))
    primary_error = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        original.content = "changed"
        raw_call["function"]["name"] = "write_file"
        raw_call["function"]["arguments"] = '{"args":{"path":"b.txt"}}'
        context["required_action_tools"][0] = "write_file"
        context["protocol_governed_enabled"] = True
        borrowed["borrowed"] = "changed extension"
        state.release.set()
        turn = await asyncio.wait_for(asyncio.shield(task), 5)
        parsed = json.loads(await asyncio.to_thread(paths[1].read_text, encoding="utf-8"))
        assert [(call.tool, call.args) for call in turn.tool_calls] == [("read_file", {"path": "a.txt"})]
        assert parsed == [{"tool": "read_file", "args": {"path": "a.txt"}}]
        assert turn.raw["total_tokens"] == 9
        assert turn.raw["extension"] is borrowed
        assert turn.raw["extension"]["borrowed"] == "changed extension"
    except BaseException as error:
        primary_error = error
        raise
    finally:
        state.release.set()
        try:
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Parser cleanup also failed: {error!r}")


async def test_parser_clock_follows_three_writes_and_skips_strict_failure(tmp_path) -> None:
    """Layer: integration. The clock samples only after all parser writes."""
    destination = _destination(tmp_path)
    calls: list[datetime] = []
    parser = ResponseParser(utc_now=lambda: calls.append(_NOW) or _NOW)
    strict = capture_turn_response({
        "content": '{"content":"","tool_calls":[{"tool":"read_file","args":{},"args":{}}]}',
        "raw": {},
    })
    with pytest.raises(ValueError, match="E_DUPLICATE_KEY"):
        await parser.parse_response(
            response=strict, destination=destination, context={"protocol_governed_enabled": True},
        )
    assert calls == []
    assert not await asyncio.to_thread(destination.output_dir.exists)

    partial = capture_turn_response({
        "content": ('```json\n{"tool":"read_file","args":{"path":"a.txt"}}\n'
                    '{"tool":"write_file","args":{"path":"b.txt"}\n```'),
        "raw": {},
    })
    turn = await parser.parse_response(response=partial, destination=destination, context={})
    assert turn.partial_parse_failure is True
    assert turn.timestamp == _NOW and calls == [_NOW]
    assert all(await asyncio.gather(*(asyncio.to_thread(path.is_file) for path in _paths(destination))))
