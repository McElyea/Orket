"""Integration: direct demo calls retain real native operations and original paths."""
import asyncio
import json
import threading
import time
from pathlib import Path

import pytest

from orket.application.services import governed_run_demo_service as demo
from tests.application.test_governed_run_demo_service import _write_test_scenario
from tests.helpers.application_root_controls import NativeHold
from tests.helpers.runtime_verification_hold import hold_stream, sqlite_response

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def seed(tmp_path):
    first, other = tmp_path / "first", tmp_path / "other"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(other.mkdir)
    await asyncio.to_thread(_write_test_scenario, first)
    await asyncio.to_thread(_write_test_scenario, other)
    await asyncio.to_thread((other / "demo-files/other.txt").write_text, "other", encoding="utf-8")
    return first, other, first / ".runs/governed-run-test"


def interrupt(task, deadline, stop):
    if stop == "cancel":
        task.cancel("first")
    elif stop == "timeout":
        deadline.reschedule(asyncio.get_running_loop().time() + 0.1)


async def observe_held(task, deadline, hold, stop, other, monkeypatch, record_property):
    assert await asyncio.to_thread(hold.entered.wait, 3)
    assert await sqlite_response(other / "observer.sqlite", record_property) < 0.5
    monkeypatch.chdir(other)
    interrupt(task, deadline, stop)
    await asyncio.sleep(0)
    if stop == "cancel":
        task.cancel("repeated")
    await asyncio.sleep(0.15 if stop == "timeout" else 0.02)
    assert not task.done(), "public call escaped admitted native work"
    hold.release.set()
    result, = await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    assert hold.finished.is_set()
    return result


def check_result(result, stop, failure, phase):
    if failure:
        if phase == "scenario":
            assert isinstance(result, ValueError)
            assert isinstance(result.__cause__, OSError)
        else:
            assert isinstance(result, OSError)
        assert "controlled native" in str(result.__cause__ if phase == "scenario" else result)
    elif stop != "none":
        assert isinstance(result, asyncio.CancelledError if stop == "cancel" else TimeoutError)
    else:
        assert result["ok"] is True


async def file_exists(path):
    return await asyncio.to_thread(path.exists)


@pytest.mark.parametrize("phase,operation", [
    ("scenario", "read"), ("scenario", "close"), ("transcript", "write"),
    ("transcript", "close"), ("inspect", "read"), ("replay", "close"),
])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_demo_file_lifetime(tmp_path, monkeypatch, phase, operation, stop, failure, record_property):
    first, other, run_dir = await seed(tmp_path)
    if phase in {"inspect", "replay"}:
        await demo.run_governed_run_scenario(first / "scenario.yaml", workspace_root=first)
    selected = first / "scenario.yaml" if phase == "scenario" else run_dir / (
        "transcript.md" if phase == "transcript" else "evidence.json")
    before = await asyncio.to_thread(selected.read_bytes) if phase in {"inspect", "replay"} else None
    hold = hold_stream(monkeypatch, selected, operation, failure=failure)
    deadline = asyncio.timeout(None)
    monkeypatch.chdir(first)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            if phase == "inspect":
                return await demo.inspect_governed_run_bundle(run_dir)
            if phase == "replay":
                return await demo.replay_governed_run_bundle(run_dir)
            return await demo.run_governed_run_scenario(Path("scenario.yaml"), workspace_root=Path())

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        check_result(result, stop, failure, phase)
        assert all(stream.closed for stream in hold.streams)
        assert not await file_exists(other / ".runs")
        if phase == "transcript":
            assert await file_exists(run_dir / "evidence.json")
            assert await file_exists(run_dir / "transcript.md")
            assert await file_exists(run_dir / "summary.md") == (stop == "none" and not failure)
        if phase in {"inspect", "replay"}:
            assert await asyncio.to_thread(selected.read_bytes) == before
        if phase == "scenario" and (stop != "none" or failure):
            assert not await file_exists(run_dir)
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("phase", ["observation", "directory"])
@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("failure", [False, True])
async def test_demo_native_lifetime(tmp_path, monkeypatch, phase, stop, failure, record_property):
    first, other, run_dir = await seed(tmp_path)
    hold = NativeHold()
    operation = "iterdir" if phase == "observation" else "mkdir"
    selected = first / "demo-files" if phase == "observation" else run_dir
    native = getattr(Path, operation)

    def held(path, *args, **kwargs):
        if path != selected or hold.entered.is_set():
            return native(path, *args, **kwargs)
        hold.wait()
        try:
            value = native(path, *args, **kwargs)
            if failure:
                raise OSError("controlled native operation failure")
            return value
        finally:
            hold.finished.set()

    monkeypatch.setattr(Path, operation, held)
    monkeypatch.chdir(first)
    deadline = asyncio.timeout(None)

    async def dispatch():
        async with asyncio.timeout(5), deadline:
            return await demo.run_governed_run_scenario(Path("scenario.yaml"), workspace_root=Path())

    task = asyncio.create_task(dispatch())
    try:
        result = await observe_held(task, deadline, hold, stop, other, monkeypatch, record_property)
        check_result(result, stop, failure, phase)
        assert not hold.expired
        assert not await file_exists(other / ".runs")
        assert await file_exists(run_dir) == (phase == "directory" or (stop == "none" and not failure))
        assert await file_exists(run_dir / "evidence.json") == (stop == "none" and not failure)
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


async def test_demo_resolve_is_owned_and_captures_relative_workspace(tmp_path, monkeypatch, record_property):
    first, other, run_dir = await seed(tmp_path)
    monkeypatch.chdir(first)
    hold = NativeHold()
    native = Path.resolve

    def held(path, *args, **kwargs):
        if hold.entered.is_set():
            return native(path, *args, **kwargs)
        hold.wait()
        try:
            return native(path, *args, **kwargs)
        finally:
            hold.finished.set()

    monkeypatch.setattr(Path, "resolve", held)
    started = time.perf_counter()
    task = asyncio.create_task(demo.run_governed_run_scenario(Path("scenario.yaml"), workspace_root=Path()))
    try:
        assert await asyncio.to_thread(hold.entered.wait, 4)
        assert hold.worker != threading.get_ident(), "path resolution ran on the event loop"
        assert await sqlite_response(other / "observer.sqlite", record_property, started) < 0.5
        monkeypatch.chdir(other)
        hold.release.set()
        result = await asyncio.wait_for(task, 5)
        assert result["ok"] and not hold.expired
        assert result["evidence"]["proposed_actions"][0]["observation"]["entries"] == ["demo-files/README.md"]
        assert await file_exists(run_dir / "summary.md")
        assert not await file_exists(other / ".runs")
        evidence = json.loads(await asyncio.to_thread((run_dir / "evidence.json").read_text, encoding="utf-8"))
        assert evidence["scenario"]["path"] == (first / "scenario.yaml").as_posix()
    finally:
        hold.release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
