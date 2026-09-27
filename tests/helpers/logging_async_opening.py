"""Real-stage and physical-readback support for integration logging observations."""
import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any

import aiosqlite

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread

__test__ = False
HOLD_SECONDS = 0.75
STAGE_TIMEOUT_SECONDS = 5.0


@dataclass
class HoldState:
    entered: threading.Event = field(default_factory=threading.Event)
    release: threading.Event = field(default_factory=threading.Event)
    finished: threading.Event = field(default_factory=threading.Event)
    watchdog_finished: threading.Event = field(default_factory=threading.Event)
    claimed_lock: threading.Lock = field(default_factory=threading.Lock)
    claimed: bool = False
    calls: int = 0
    worker: int | None = None
    expired: bool = False
    auto_released: bool = False
    watchdog_error: str | None = None
    records: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class LogObservation:
    log_result: object
    sqlite_result: object
    records: list[dict[str, Any]]
    loop_thread: int
    stage_finished: bool
    timed_out: bool
    watchdog_alive: bool


def _enter_hold(state: HoldState) -> None:
    with state.claimed_lock:
        if state.claimed:
            return
        state.claimed = True
        state.calls += 1
    state.worker = threading.get_ident()
    state.entered.set()
    try:
        state.expired = not state.release.wait(STAGE_TIMEOUT_SECONDS)
    finally:
        state.finished.set()


def hold_path_stage(monkeypatch: Any, workspace: Path, stage: str) -> HoldState:
    state = HoldState()
    if stage == "resolve":
        original_resolve = Path.resolve

        def held_resolve(path: Path, *args: Any, **kwargs: Any) -> Path:
            resolved = original_resolve(path, *args, **kwargs)
            if path == workspace:
                _enter_hold(state)
            return resolved

        monkeypatch.setattr(Path, "resolve", held_resolve)
        return state
    if stage == "mkdir":
        original_mkdir = Path.mkdir

        def held_mkdir(path: Path, *args: Any, **kwargs: Any) -> None:
            original_mkdir(path, *args, **kwargs)
            if path == workspace:
                _enter_hold(state)

        monkeypatch.setattr(Path, "mkdir", held_mkdir)
        return state
    raise ValueError(f"unsupported path stage: {stage}")


class HeldStandardHandler(logging.Handler):
    def __init__(self, state: HoldState, event: str) -> None:
        super().__init__()
        self._state = state
        self._event = event

    def emit(self, record: logging.LogRecord) -> None:
        if record.name == "orket" and record.getMessage() == self._event:
            _enter_hold(self._state)


def held_subscriber(state: HoldState, event: str) -> Callable[[dict[str, Any]], None]:
    def subscriber(record: dict[str, Any]) -> None:
        if record.get("event") != event:
            return
        state.records.append(json.loads(json.dumps(record, default=str)))
        _enter_hold(state)

    return subscriber


def wait_for_stage_entry(state: HoldState) -> bool:
    deadline = time.monotonic() + STAGE_TIMEOUT_SECONDS
    while True:
        if state.entered.wait(0.01):
            return True
        if state.release.is_set() or time.monotonic() >= deadline:
            return False


def _release_after_entry(state: HoldState) -> None:
    try:
        if not wait_for_stage_entry(state):
            if not state.release.is_set():
                state.watchdog_error = "target stage was not entered"
                state.release.set()
            return
        if not state.release.wait(HOLD_SECONDS):
            state.auto_released = True
            state.release.set()
    finally:
        state.watchdog_finished.set()


def release_watchdog(state: HoldState) -> threading.Thread:
    return threading.Thread(
        target=partial(_release_after_entry, state),
        name="orket-logging-opening-watchdog",
        daemon=False,
    )


async def start_fixture_thread(thread: threading.Thread, *, label: str) -> None:
    await run_owned_thread(thread.start, label=f"{label}-start")


async def join_fixture_thread(thread: threading.Thread, *, label: str) -> None:
    if thread.ident is None:
        return
    await run_owned_thread(thread.join, label=f"{label}-join")


async def wait_for_fixture_event(event: threading.Event, *, label: str) -> bool:
    return await run_owned_thread(
        partial(event.wait, STAGE_TIMEOUT_SECONDS),
        label=label,
    )


async def sqlite_observation(database: Path, started: float) -> dict[str, Any]:
    async with aiosqlite.connect(database) as connection:
        await connection.execute("CREATE TABLE probe (value INTEGER NOT NULL)")
        await connection.execute("INSERT INTO probe(value) VALUES (42)")
        await connection.commit()
        cursor = await connection.execute("SELECT value FROM probe")
        row = await cursor.fetchone()
        await cursor.close()
    return {"elapsed": time.perf_counter() - started, "row": row}


def _read_event_records(
    path: Path,
    event: str,
    *,
    allow_incomplete_trailing: bool,
) -> tuple[list[dict[str, Any]], bool]:
    try:
        lines = path.read_bytes().splitlines(keepends=True)
    except FileNotFoundError:
        return [], False
    records: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        is_unterminated = index == len(lines) - 1 and not line.endswith((b"\n", b"\r"))
        if is_unterminated:
            if allow_incomplete_trailing:
                return records, True
            raise ValueError("unterminated logging JSONL record")
        record = json.loads(line)
        if isinstance(record, dict) and record.get("event") == event:
            records.append(record)
    return records, False


async def _owned_event_records(
    path: Path,
    event: str,
    *,
    allow_incomplete_trailing: bool,
) -> tuple[list[dict[str, Any]], bool]:
    return await run_owned_thread(
        partial(
            _read_event_records,
            path,
            event,
            allow_incomplete_trailing=allow_incomplete_trailing,
        ),
        label="logging-opening-log-read",
    )


async def wait_for_event_records(
    path: Path,
    event: str,
    budget_seconds: float = STAGE_TIMEOUT_SECONDS,
) -> list[dict[str, Any]]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_seconds
    while True:
        records, trailing_pending = await _owned_event_records(
            path,
            event,
            allow_incomplete_trailing=True,
        )
        if records and not trailing_pending:
            return records
        if loop.time() >= deadline:
            if trailing_pending:
                records, _ = await _owned_event_records(
                    path,
                    event,
                    allow_incomplete_trailing=False,
                )
            return records
        await asyncio.sleep(0.01)


def _call_log(
    log: Callable[..., None],
    event: str,
    payload: dict[str, Any],
    workspace: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    log(event, payload, workspace=workspace)
    return {
        "elapsed": time.perf_counter() - started,
        "thread": threading.get_ident(),
    }


async def _invoke_log(
    log: Callable[..., None],
    event: str,
    payload: dict[str, Any],
    workspace: Path,
    native: bool,
) -> dict[str, Any]:
    if native:
        return await run_owned_thread(
            partial(_call_log, log, event, payload, workspace),
            label="logging-opening-native-log",
        )
    return _call_log(log, event, payload, workspace)


async def _collect_tasks(
    log_task: asyncio.Task[dict[str, Any]],
    sqlite_task: asyncio.Task[dict[str, Any]],
) -> tuple[object, object, bool]:
    try:
        log_result, sqlite_result = await asyncio.wait_for(
            asyncio.gather(log_task, sqlite_task, return_exceptions=True),
            timeout=STAGE_TIMEOUT_SECONDS + 2.0,
        )
        return log_result, sqlite_result, False
    except TimeoutError as error:
        return error, error, True


async def _settle_async_tasks(tasks: list[asyncio.Task[Any]]) -> None:
    async def settle() -> None:
        await asyncio.gather(*tasks, return_exceptions=True)

    await run_owned_io(
        settle,
        label="logging-opening-task-settlement",
        preserve_failure=True,
    )


async def observe_log_call(
    *,
    log: Callable[..., None],
    event: str,
    payload: dict[str, Any],
    workspace: Path,
    state: HoldState,
    native: bool = False,
) -> LogObservation:
    loop_thread = threading.get_ident()
    watchdog = release_watchdog(state)
    log_task: asyncio.Task[dict[str, Any]] | None = None
    sqlite_task: asyncio.Task[dict[str, Any]] | None = None
    try:
        await start_fixture_thread(watchdog, label="logging-opening-watchdog")
        started = time.perf_counter()
        log_task = asyncio.create_task(_invoke_log(log, event, payload, workspace, native))
        sqlite_task = asyncio.create_task(
            sqlite_observation(workspace.parent / f"{event}.sqlite3", started)
        )
        log_result, sqlite_result, timed_out = await _collect_tasks(log_task, sqlite_task)
        stage_finished = await wait_for_fixture_event(
            state.finished,
            label="logging-opening-stage-finished",
        )
        records = await wait_for_event_records(workspace / "orket.log", event)
    finally:
        state.release.set()
        tasks = [task for task in (log_task, sqlite_task) if task is not None]
        for task in tasks:
            if not task.done():
                task.cancel()
        try:
            await _settle_async_tasks(tasks)
        finally:
            await join_fixture_thread(watchdog, label="logging-opening-watchdog")
    return LogObservation(
        log_result=log_result,
        sqlite_result=sqlite_result,
        records=records,
        loop_thread=loop_thread,
        stage_finished=stage_finished,
        timed_out=timed_out,
        watchdog_alive=watchdog.is_alive(),
    )
