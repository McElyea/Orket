"""Layer: integration. Reviewed diagnostic for MessageBuilder read-context ownership.

This ignored module is preparatory evidence for the boundary after packet 2. It is
intended to be copied unchanged into exact source and installed test harnesses.
"""

import asyncio
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import aiosqlite
import pytest

from orket.application.workflows.turn_message_builder import MessageBuilder
from orket.schema import IssueConfig, RoleConfig
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.helpers.turn_artifacts import prepare_message_fixture
from tests.integration.test_async_file_native_lifetime import hold_native_open

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
_READ_PATH = "agent_output/requirements.txt"
_EXPECTED_MAX_PRELOADED_READ_CONTEXT_CHARS = 4000


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-READ", name="Read context", seat="reviewer", status="in_progress")


def _role() -> RoleConfig:
    return RoleConfig(
        id="reviewer",
        name="reviewer",
        description="Reviews artifacts",
        prompt="Review the admitted artifact",
        tools=["read_file", "add_issue_comment", "update_issue_status"],
    )


def _context() -> dict[str, object]:
    return {
        "issue_id": "ISSUE-READ",
        "role": "reviewer",
        "required_action_tools": ["read_file", "add_issue_comment", "update_issue_status"],
        "required_statuses": ["code_review"],
        "required_read_paths": [_READ_PATH],
        "required_write_paths": [],
        "required_comment_min_length": 80,
        "history": [],
    }


def _rendered(messages: list[dict[str, str]]) -> str:
    return "\n".join(message["content"] for message in messages)


async def _write_bytes(path: Path, content: bytes) -> None:
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_bytes, content)


async def _assert_bytes_unchanged(path: Path, expected: bytes) -> None:
    actual = await asyncio.to_thread(path.read_bytes)
    assert actual == expected


def _raise_cleanup_errors(errors: list[BaseException]) -> None:
    if not errors:
        return
    first, *rest = errors
    for error in rest:
        first.add_note(f"Additional cleanup failure: {error!r}")
    raise first


def _hold_resolve(monkeypatch, target: Path, *, enabled: bool):
    """Hold only the first target resolve for opening diagnosis, not repair acceptance."""
    state = SimpleNamespace(
        entered=threading.Event(),
        release=threading.Event(),
        finished=threading.Event(),
        threads=[],
        timers=[],
    )
    original = Path.resolve

    def observed(path, *args, **options):
        # MessageBuilder resolves this path more than once. Holding only the first
        # gives a bounded opening counterexample; it cannot prove every site repaired.
        if enabled and path == target and not state.entered.is_set():
            state.threads.append(threading.get_ident())
            state.entered.set()
            timer = threading.Timer(0.8, state.release.set)
            state.timers.append(timer)
            timer.start()
            try:
                assert state.release.wait(5), "Native path observation was not released"
            finally:
                state.finished.set()
        return original(path, *args, **options)

    monkeypatch.setattr(Path, "resolve", observed)
    return state


async def _sqlite_elapsed(database: Path, started: float) -> float:
    async with aiosqlite.connect(database) as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    return time.perf_counter() - started


async def _settle_metadata_probe(task, probe, state, target: Path, before: bytes) -> None:
    errors: list[BaseException] = []
    state.release.set()
    try:
        await asyncio.wait_for(asyncio.gather(task, probe, return_exceptions=True), 5)
    except BaseException as error:
        errors.append(error)
    for timer in state.timers:
        timer.cancel()
        try:
            await asyncio.to_thread(timer.join, 5)
        except BaseException as error:
            errors.append(error)
    try:
        assert all(not timer.is_alive() for timer in state.timers)
    except BaseException as error:
        errors.append(error)
    if state.entered.is_set():
        try:
            assert await asyncio.to_thread(state.finished.wait, 5)
        except BaseException as error:
            errors.append(error)
    try:
        await _assert_bytes_unchanged(target, before)
    except BaseException as error:
        errors.append(error)
    _raise_cleanup_errors(errors)


async def _settle_handle_probe(task, state, timer, target: Path, before: bytes) -> None:
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
        await _assert_bytes_unchanged(target, before)
    except BaseException as error:
        errors.append(error)
    _raise_cleanup_errors(errors)


async def test_message_builder_preloads_and_truncates_real_file(tmp_path: Path) -> None:
    target = tmp_path / _READ_PATH
    normalized_prefix = "line-one\n"
    inside_boundary = "inside-4000-boundary"
    filler = "x" * (
        _EXPECTED_MAX_PRELOADED_READ_CONTEXT_CHARS
        - len(normalized_prefix)
        - len(inside_boundary)
    )
    outside_boundary = "outside-4000-boundary"
    tail = "tail-must-not-be-preloaded"
    normalized = normalized_prefix + filler + inside_boundary + outside_boundary + "\n" + tail
    physical = (
        "line-one\r\n" + filler + inside_boundary + outside_boundary + "\r\n" + tail
    ).encode("utf-8")
    await _write_bytes(target, physical)
    before = await asyncio.to_thread(target.read_bytes)
    primary_error: BaseException | None = None

    try:
        messages = await prepare_message_fixture(MessageBuilder(tmp_path),
            issue=_issue(), role=_role(), context=_context()
        )
        rendered = _rendered(messages)
        expected_slice = normalized[:_EXPECTED_MAX_PRELOADED_READ_CONTEXT_CHARS]
        expected_block = f"Path: {_READ_PATH}\nContent:\n{expected_slice}\n[truncated]"

        assert len(expected_slice) == _EXPECTED_MAX_PRELOADED_READ_CONTEXT_CHARS
        assert expected_slice.endswith(inside_boundary)
        assert normalized[_EXPECTED_MAX_PRELOADED_READ_CONTEXT_CHARS :].startswith(
            outside_boundary
        )
        assert expected_block in rendered
        assert "\r" not in rendered
        assert outside_boundary not in rendered
        assert tail not in rendered
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _assert_bytes_unchanged(target, before)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Physical byte readback also failed: {cleanup_error!r}")


@pytest.mark.parametrize("held", [False, True], ids=["healthy", "native-hold"])
async def test_message_read_metadata_preserves_sqlite_response(
    tmp_path: Path, monkeypatch, record_property, held: bool
) -> None:
    target = tmp_path / _READ_PATH
    await _write_bytes(target, b"metadata responsiveness\n")
    before = await asyncio.to_thread(target.read_bytes)
    state = _hold_resolve(monkeypatch, target, enabled=held)
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
        assert "metadata responsiveness" in _rendered(messages)
        if held:
            assert state.entered.is_set() and state.finished.is_set()
            assert state.threads == [state.threads[0]]
            assert state.threads[0] != threading.get_ident()
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_metadata_probe(task, probe, state, target, before)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Metadata cleanup also failed: {cleanup_error!r}")


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_message_read_handle_settles_before_interrupted_return(
    tmp_path: Path, monkeypatch, record_property, stop: str
) -> None:
    target = tmp_path / _READ_PATH
    await _write_bytes(target, b"owned read context\n")
    before = await asyncio.to_thread(target.read_bytes)
    state = SimpleNamespace(
        entered=threading.Event(), release=threading.Event(), finished=threading.Event(), streams=[]
    )
    hold_native_open(monkeypatch, target, state, failure=False)
    deadline = asyncio.timeout(None)

    async def operation():
        async with asyncio.timeout(5), deadline:
            return await prepare_message_fixture(MessageBuilder(tmp_path),
                issue=_issue(), role=_role(), context=_context()
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
        state.release.set()
        expected = TimeoutError if stop == "timeout" else asyncio.CancelledError
        with pytest.raises(expected):
            await asyncio.wait_for(asyncio.shield(task), 5)
        assert state.finished.is_set() and state.streams
        assert all(stream.closed for stream in state.streams)
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            await _settle_handle_probe(task, state, timer, target, before)
        except BaseException as cleanup_error:
            if primary_error is None:
                raise
            primary_error.add_note(f"Handle cleanup also failed: {cleanup_error!r}")
