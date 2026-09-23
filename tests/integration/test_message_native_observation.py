"""Layer: integration. Message read metadata and missing-log native ownership."""

import asyncio
import io
import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiofiles.threadpool
import aiosqlite
import pytest

import orket.logging as logging_module
from orket.application.workflows.turn_message_builder import MessageBuilder
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import prepare_message_fixture
from tests.integration.test_async_file_native_lifetime import hold_native_open
from tests.integration.test_direct_metadata_lifetime import held_metadata
from tests.integration.test_message_read_ownership import _context, _issue, _role, _write_bytes

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATH = "agent_output/requirements.txt"
_MISSING_PATH = "agent_output/missing-requirements.txt"


def _metadata_observer(
    monkeypatch,
    *,
    relevant: set[Path],
    held: tuple[str, Path] | None,
    auto_release: bool,
):
    state = SimpleNamespace(
        observations=[],
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        timers=[],
    )
    originals = {name: getattr(Path, name) for name in ("resolve", "exists", "is_file")}

    def replacement(name):
        original = originals[name]

        def observed(path, *args, **options):
            candidate = Path(path)
            if candidate in relevant:
                state.observations.append((name, candidate, threading.get_ident()))
                if held == (name, candidate) and not state.entered.is_set():
                    state.entered.set()
                    if auto_release:
                        timer = threading.Timer(0.8, state.release.set)
                        state.timers.append(timer)
                        timer.start()
                    try:
                        assert state.release.wait(5), "Metadata fixture was not released"
                        return original(path, *args, **options)
                    finally:
                        state.finished.set()
            return original(path, *args, **options)

        return observed

    for name in originals:
        monkeypatch.setattr(Path, name, replacement(name))
    return state


def _held_site(site: str | None, workspace: Path, target: Path):
    return {
        None: None,
        "root-resolve": ("resolve", workspace),
        "target-resolve": ("resolve", target),
        "target-exists": ("exists", target),
        "target-is-file": ("is_file", target),
    }[site]


async def _sqlite_elapsed(database: Path, started: float) -> float:
    async with aiosqlite.connect(database) as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    return time.perf_counter() - started


async def _settle_metadata(tasks, state, timers, target: Path, expected: bytes) -> None:
    errors: list[BaseException] = []
    state.release.set()
    for timer in [*state.timers, *timers]:
        timer.cancel()
        try:
            await asyncio.to_thread(timer.join, 5)
        except BaseException as error:
            errors.append(error)
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
    except BaseException as error:
        errors.append(error)
    if state.entered.is_set():
        try:
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            errors.append(error)
    try:
        assert all(not timer.is_alive() for timer in [*state.timers, *timers])
        assert await asyncio.to_thread(target.read_bytes) == expected
    except BaseException as error:
        errors.append(error)
    if errors:
        first, *rest = errors
        for error in rest:
            first.add_note(f"Additional cleanup failure: {error!r}")
        raise first


def _assert_metadata_threads(state, loop_thread: int, workspace: Path, target: Path) -> None:
    assert state.observations
    assert all(thread != loop_thread for _, _, thread in state.observations)
    observed = {(method, path) for method, path, _ in state.observations}
    assert ("resolve", workspace) in observed
    assert ("resolve", target) in observed
    assert ("exists", target) in observed
    assert ("is_file", target) in observed


@pytest.mark.parametrize(
    "site",
    [None, "root-resolve", "target-resolve", "target-exists", "target-is-file"],
    ids=["healthy", "root-resolve", "target-resolve", "target-exists", "target-is-file"],
)
async def test_message_read_observes_all_metadata_off_loop(
    tmp_path: Path, monkeypatch, record_property, site: str | None
) -> None:
    target = tmp_path / _READ_PATH
    expected = b"all metadata is physically observed\n"
    await _write_bytes(target, expected)
    state = _metadata_observer(
        monkeypatch,
        relevant={tmp_path, tmp_path / "agent_output", target},
        held=_held_site(site, tmp_path, target),
        auto_release=True,
    )
    started = time.perf_counter()
    task = asyncio.create_task(
        prepare_message_fixture(MessageBuilder(tmp_path), issue=_issue(), role=_role(), context=_context())
    )
    probe = asyncio.create_task(_sqlite_elapsed(tmp_path / "responsive.sqlite3", started))
    primary_error: BaseException | None = None
    try:
        messages, elapsed = await asyncio.wait_for(asyncio.gather(task, probe), 5)
        record_property("responsive_sqlite_seconds", elapsed)
        assert elapsed < 0.5
        assert "all metadata is physically observed" in "\n".join(row["content"] for row in messages)
        _assert_metadata_threads(state, threading.get_ident(), tmp_path, target)
        if site is not None:
            assert state.entered.is_set() and state.finished.is_set()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_metadata([task, probe], state, [], target, expected)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Metadata cleanup also failed: {cleanup_error!r}")


def _observe_later_stages(monkeypatch, target: Path):
    state = SimpleNamespace(reads=[], logs=[], active=True)
    original_open = io.open
    original_append = logging_module._append_line_sync
    original_setup = logging_module.setup_logging

    def observed_open(file, *args, **options):
        mode = options.get("mode", args[0] if args else "r")
        if state.active and not isinstance(file, int) and Path(file) == target and "r" in mode:
            state.reads.append(threading.get_ident())
        return original_open(file, *args, **options)

    def observed_append(path, line):
        if state.active:
            state.logs.append(("append", Path(path), threading.get_ident()))
        return original_append(path, line)

    def observed_setup(workspace):
        if state.active:
            state.logs.append(("setup", Path(workspace), threading.get_ident()))
        return original_setup(workspace)

    monkeypatch.setattr(io, "open", observed_open)
    monkeypatch.setattr(aiofiles.threadpool, "sync_open", observed_open)
    monkeypatch.setattr(logging_module, "_append_line_sync", observed_append)
    monkeypatch.setattr(logging_module, "setup_logging", observed_setup)
    return state


@pytest.mark.parametrize("site", ["root-resolve", "target-resolve", "target-exists", "target-is-file"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_interrupted_metadata_stops_read_and_log_stages(
    tmp_path: Path, monkeypatch, record_property, site: str, stop: str
) -> None:
    target = tmp_path / _READ_PATH
    expected = b"later read must not be admitted\n"
    await _write_bytes(target, expected)
    context = _context()
    context["required_read_paths"] = [_READ_PATH, _MISSING_PATH]
    context["prompt_metadata"] = {}
    context["prompt_layers"] = {}
    state = _metadata_observer(
        monkeypatch,
        relevant={tmp_path, tmp_path / "agent_output", target, tmp_path / _MISSING_PATH},
        held=_held_site(site, tmp_path, target),
        auto_release=False,
    )
    later = _observe_later_stages(monkeypatch, target)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await prepare_message_fixture(MessageBuilder(tmp_path),
                issue=_issue(), role=_role(), context=context
            )

    timer = threading.Timer(0.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        if stop == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.03)
        assert not task.done() and not state.finished.is_set()
        assert not later.reads and not later.logs
        state.release.set()
        expected_error = TimeoutError if stop == "timeout" else asyncio.CancelledError
        with pytest.raises(expected_error):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set() and not later.reads and not later.logs
        assert "prompt_packet_compacted" not in context.get("prompt_metadata", {})
        assert "packet_compaction" not in context["prompt_layers"]
        assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        later.active = False
        try:
            await _settle_metadata([task], state, [timer], target, expected)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Interrupted metadata cleanup also failed: {cleanup_error!r}")


async def _settle_log(task, state, timer, target: Path, expected: bytes) -> None:
    errors: list[BaseException] = []
    state.release.set()
    timer.cancel()
    try:
        await asyncio.to_thread(timer.join, 5)
    except BaseException as error:
        errors.append(error)
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
    except BaseException as error:
        errors.append(error)
    try:
        await asyncio.wait_for(asyncio.to_thread(logging_module._log_write_queue.join), 5)
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
    except BaseException as error:
        errors.append(error)
    try:
        assert await asyncio.to_thread(target.read_bytes) == expected
    except BaseException as error:
        errors.append(error)
    if errors:
        first, *rest = errors
        for error in rest:
            first.add_note(f"Additional cleanup failure: {error!r}")
        raise first


def _hold_log_boundary(monkeypatch, workspace: Path, log_path: Path, boundary: str, failure: bool):
    if boundary == "directory":
        state = held_metadata(monkeypatch, workspace, "mkdir", failure)
        state.streams = []
        return state
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[]
    )
    hold_native_open(monkeypatch, log_path, state, failure=failure)
    return state


async def _assert_missing_log(log_path: Path, outcome: str) -> None:
    if outcome == "cancel-failure":
        exists = await asyncio.to_thread(log_path.exists)
        raw = await asyncio.to_thread(log_path.read_bytes) if exists else b""
        assert raw == b""
        return
    raw = await asyncio.to_thread(log_path.read_bytes)
    records = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    record, = [row for row in records if row.get("event") == "preflight_missing_read_paths"]
    assert record["data"]["missing_required_read_paths"] == [_MISSING_PATH]


@pytest.mark.parametrize("boundary", ["directory", "write"])
@pytest.mark.parametrize("outcome", ["cancel", "timeout", "cancel-failure"])
async def test_missing_input_log_is_owned_and_physically_observed(
    tmp_path: Path, monkeypatch, record_property, boundary: str, outcome: str
) -> None:
    monkeypatch.chdir(tmp_path)
    workspace = tmp_path / "workspace"
    log_path = workspace / "orket.log"
    target, expected = workspace / _READ_PATH, b"retained logging input\n"
    await _write_bytes(target, expected)
    context = _context()
    context["required_read_paths"] = [_READ_PATH, _MISSING_PATH]
    context["prompt_metadata"] = {}
    context["prompt_layers"] = {}
    state = _hold_log_boundary(
        monkeypatch,
        workspace,
        log_path,
        boundary,
        outcome == "cancel-failure",
    )
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await prepare_message_fixture(MessageBuilder(workspace),
                issue=_issue(), role=_role(), context=context
            )

    timer = threading.Timer(0.8, state.release.set)
    timer.start()
    task = asyncio.create_task(operation())
    primary_error: BaseException | None = None
    try:
        assert await asyncio.to_thread(state.entered.wait, 5)
        await responsive_sqlite(tmp_path / "responsive.sqlite3", record_property)
        if outcome == "timeout":
            deadline.reschedule(asyncio.get_running_loop().time() + 0.01)
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.03)
        assert not task.done() and not state.finished.is_set()
        state.release.set()
        expected_error = OSError if outcome == "cancel-failure" else (
            TimeoutError if outcome == "timeout" else asyncio.CancelledError
        )
        with pytest.raises(expected_error):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set()
        if boundary == "directory":
            assert state.threads == [state.threads[0]]
            assert state.threads[0] != threading.get_ident()
        else:
            assert state.streams and all(stream.closed for stream in state.streams)
        assert "prompt_packet_compacted" not in context["prompt_metadata"]
        await asyncio.wait_for(asyncio.to_thread(logging_module._log_write_queue.join), 5)
        await _assert_missing_log(log_path, outcome)
        assert await asyncio.to_thread(target.read_bytes) == expected
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_log(task, state, timer, target, expected)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Missing-log cleanup also failed: {cleanup_error!r}")
