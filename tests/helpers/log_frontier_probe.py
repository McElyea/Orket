"""Isolated real-queue controls for the process-global log writer."""
from __future__ import annotations

import asyncio
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

import psutil

import orket.logging as logging_module
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger

__test__ = False
WAIT_SECONDS = 4.0
_fatal_thread: dict[str, Any] = {}


def _wait(event: threading.Event, label: str) -> None:
    if not event.wait(WAIT_SECONDS):
        raise TimeoutError(f"fixture watchdog expired: {label}")


def _exception_data(exc: BaseException) -> dict[str, Any]:
    cause = exc.__cause__
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "cause_type": type(cause).__name__ if cause is not None else None,
        "cause_message": str(cause) if cause is not None else None,
    }


def _call_frontier() -> dict[str, Any]:
    try:
        logging_module.settle_log_write_frontier()
    except BaseException as exc:  # subprocess observation boundary
        return {"status": "error", "error": _exception_data(exc)}
    return {"status": "settled"}


def _start_frontier() -> tuple[threading.Thread, threading.Event, dict[str, Any]]:
    done = threading.Event()
    result: dict[str, Any] = {}

    def invoke() -> None:
        try:
            result.update(_call_frontier())
        finally:
            done.set()

    thread = threading.Thread(target=invoke, name="fixture-log-frontier")
    thread.start()
    return thread, done, result


def _finish_thread(thread: threading.Thread, done: threading.Event, label: str) -> None:
    _wait(done, f"{label}-done")
    thread.join(WAIT_SECONDS)
    if thread.is_alive():
        raise TimeoutError(f"fixture watchdog expired: {label}-join")


def _admit(path: Path, *events: str) -> None:
    async def publish() -> None:
        for event in events:
            logging_module._append_json_record(path, {"event": event})

    asyncio.run(publish())


def _events(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [json.loads(line)["event"] for line in path.read_text(encoding="utf-8").splitlines()]


def _writer_data() -> dict[str, Any] | None:
    writer = logging_module._log_writer_thread
    if writer is None:
        return None
    return {
        "name": writer.name,
        "ident": writer.ident,
        "native_id": getattr(writer, "native_id", None),
        "daemon": writer.daemon,
        "alive": writer.is_alive(),
    }


class _MarkerObserver:
    def __init__(self) -> None:
        self.attempted = threading.Event()
        self.admitted = threading.Event()
        self._lock = threading.Lock()
        self.attempts = 0
        self.admissions = 0
        queue_owner = logging_module._log_write_queue
        self._put = queue_owner.put_nowait
        queue_owner.put_nowait = self._observe

    def _observe(self, item: Any) -> None:
        marker = isinstance(item, logging_module._LogWriteFrontier)
        if marker:
            with self._lock:
                self.attempts += 1
            self.attempted.set()
        self._put(item)
        if marker:
            with self._lock:
                self.admissions += 1
            self.admitted.set()

    def _data(self) -> dict[str, int]:
        with self._lock:
            return {"attempts": self.attempts, "admissions": self.admissions}


class _AppendRig:
    def __init__(self, path: Path, *, held: set[str], failures: dict[str, str]) -> None:
        self.path = path
        self.entered = {name: threading.Event() for name in held}
        self.release = {name: threading.Event() for name in held}
        self.finished = {name: threading.Event() for name in held}
        self.failures = failures
        self._calls: list[str] = []
        self._lock = threading.Lock()
        self._append = logging_module._append_line_sync
        logging_module._append_line_sync = self._observed_append

    def _observed_append(self, path: Path, line: str) -> None:
        event = str(json.loads(line)["event"])
        with self._lock:
            self._calls.append(event)
        if event in self.entered:
            self.entered[event].set()
            _wait(self.release[event], f"release-{event}")
        failure = self.failures.get(event)
        if failure == "oserror":
            raise OSError("controlled optional append failure")
        if failure == "fatal":
            raise ValueError("controlled fatal log writer failure")
        self._append(path, line)
        if event in self.finished:
            self.finished[event].set()

    def _call_data(self) -> list[str]:
        with self._lock:
            return list(self._calls)

    def _release_all(self) -> None:
        for event in self.release.values():
            event.set()


def _base(scenario: str, path: Path) -> dict[str, Any]:
    process = psutil.Process()
    return {
        "schema_version": "log_frontier_probe.v1",
        "scenario": scenario,
        "process_identity": {"pid": os.getpid(), "create_time": process.create_time()},
        "logging_origin": str(Path(logging_module.__file__).resolve()),
        "path": str(path),
        "report_path": str(path.parent / "probe-report.json"),
        "queue_max": logging_module._log_write_queue.maxsize,
    }


def _unprepared_reuse(root: Path) -> dict[str, Any]:
    path = root / "events.jsonl"
    marker = _MarkerObserver()
    before = _writer_data()
    drops_before = logging_module.dropped_log_entry_count()
    first_settlement = _call_frontier()
    first_writer = logging_module._log_writer_thread
    _admit(path, "queued-after-first-settlement")
    second_settlement = _call_frontier()
    observation = _base("unprepared-reuse", path)
    observation.update(
        before=before,
        first_settlement=first_settlement,
        second_settlement=second_settlement,
        same_writer=first_writer is logging_module._log_writer_thread,
        writer=_writer_data(),
        writer_name_count=sum(t.name == "orket-log-writer" for t in threading.enumerate()),
        marker=marker._data(),
        append_events=_events(path),
        drops_before=drops_before,
        drops_after=logging_module.dropped_log_entry_count(),
    )
    return observation


def _loop_refusal(root: Path) -> dict[str, Any]:
    path = root / "events.jsonl"
    marker = _MarkerObserver()
    before = {"writer": _writer_data(), "queue_size": logging_module._log_write_queue.qsize(),
              "drops": logging_module.dropped_log_entry_count()}

    async def refuse() -> dict[str, Any]:
        return _call_frontier()

    refusal = asyncio.run(refuse())
    after = {"writer": _writer_data(), "queue_size": logging_module._log_write_queue.qsize(),
             "drops": logging_module.dropped_log_entry_count()}
    observation = _base("loop-refusal", path)
    observation.update(before=before, after=after, refusal=refusal, marker=marker._data())
    return observation


def _optional_oserror(root: Path) -> dict[str, Any]:
    path = root / "events.jsonl"
    rig = _AppendRig(path, held=set(), failures={"optional-oserror": "oserror"})
    marker = _MarkerObserver()
    drops_before = logging_module.dropped_log_entry_count()
    _admit(path, "optional-oserror")
    settlement = _call_frontier()
    observation = _base("optional-oserror", path)
    observation.update(
        settlement=settlement,
        calls=rig._call_data(),
        physical_events=_events(path),
        marker=marker._data(),
        writer=_writer_data(),
        drops_before=drops_before,
        drops_after=logging_module.dropped_log_entry_count(),
    )
    return observation


def _full_queue_cutoff(root: Path) -> dict[str, Any]:
    path = root / "events.jsonl"
    held = {"held-first", "prior-one", "prior-two", "later"}
    rig = _AppendRig(path, held=held, failures={})
    marker = _MarkerObserver()
    frontier: tuple[threading.Thread, threading.Event, dict[str, Any]] | None = None
    drops_before = logging_module.dropped_log_entry_count()
    try:
        _admit(path, "held-first")
        _wait(rig.entered["held-first"], "held-first-entered")
        _admit(path, "prior-one", "prior-two")
        queue_full = logging_module._log_write_queue.full()
        frontier = _start_frontier()
        _wait(marker.attempted, "full-marker-attempted")
        blocked_while_full = not frontier[1].is_set() and not marker.admitted.is_set()
        rig.release["held-first"].set()
        _wait(rig.entered["prior-one"], "prior-one-entered")
        _wait(marker.admitted, "full-marker-admitted")
        drops_after_marker_admission = logging_module.dropped_log_entry_count()
        rig.release["prior-one"].set()
        _wait(rig.entered["prior-two"], "prior-two-entered")
        _admit(path, "later")
        drops_before_forced_drop = logging_module.dropped_log_entry_count()
        _admit(path, "ordinary-drop-while-marker-pending")
        forced_drop_delta = logging_module.dropped_log_entry_count() - drops_before_forced_drop
        rig.release["prior-two"].set()
        _wait(rig.entered["later"], "later-entered")
        _wait(frontier[1], "frontier-before-later-release")
        cutoff = frontier[1].is_set() and not rig.finished["later"].is_set()
        before_later_release = _events(path)
        rig.release["later"].set()
        _wait(rig.finished["later"], "later-finished")
        _finish_thread(frontier[0], frontier[1], "frontier")
        final_settlement = _call_frontier()
        observation = _base("full-queue-cutoff", path)
        observation.update(
            queue_full=queue_full, blocked_while_full=blocked_while_full,
            frontier=frontier[2], cutoff=cutoff, before_later_release=before_later_release,
            physical_events=_events(path), calls=rig._call_data(), marker=marker._data(),
            final_settlement=final_settlement, drops_before=drops_before,
            drops_after_marker_admission=drops_after_marker_admission,
            forced_drop_delta=forced_drop_delta,
            drops_after=logging_module.dropped_log_entry_count(), writer=_writer_data(),
        )
        return observation
    finally:
        rig._release_all()
        if frontier is not None:
            _finish_thread(frontier[0], frontier[1], "frontier-cleanup")


def _capture_fatal_thread(args: threading.ExceptHookArgs) -> None:
    _fatal_thread.update(
        thread_name=args.thread.name if args.thread is not None else None,
        error=_exception_data(args.exc_value),
    )


def _fatal_writer(root: Path, phase: str) -> dict[str, Any]:
    path = root / "events.jsonl"
    rig = _AppendRig(path, held={"fatal-first"}, failures={"fatal-first": "fatal"})
    marker = _MarkerObserver()
    frontier: tuple[threading.Thread, threading.Event, dict[str, Any]] | None = None
    threading.excepthook = _capture_fatal_thread
    try:
        _admit(path, "fatal-first")
        _wait(rig.entered["fatal-first"], "fatal-first-entered")
        writer = logging_module._log_writer_thread
        if phase == "before-admission":
            _admit(path, "queued-one", "queued-two")
        queue_full = logging_module._log_write_queue.full()
        frontier = _start_frontier()
        _wait(marker.attempted, "fatal-marker-attempted")
        if phase == "after-admission":
            _wait(marker.admitted, "fatal-marker-admitted")
        admitted_before_failure = marker.admitted.is_set()
        rig.release["fatal-first"].set()
        _finish_thread(frontier[0], frontier[1], "fatal-frontier")
        if writer is None:
            raise AssertionError("writer was not started")
        writer.join(WAIT_SECONDS)
        if writer.is_alive():
            raise TimeoutError("fixture watchdog expired: fatal-writer-join")
        second_settlement = _call_frontier()
        drops_before_optional = logging_module.dropped_log_entry_count()
        optional_after_dead = {"status": "accepted"}
        try:
            _admit(path, "optional-after-dead-one", "optional-after-dead-two")
        except BaseException as exc:  # subprocess observation boundary
            optional_after_dead = {"status": "error", "error": _exception_data(exc)}
        observation = _base(f"fatal-{phase}", path)
        observation.update(
            queue_full=queue_full, admitted_before_failure=admitted_before_failure,
            frontier=frontier[2], second_settlement=second_settlement,
            optional_after_dead=optional_after_dead,
            drops_before_optional=drops_before_optional,
            drops_after_optional=logging_module.dropped_log_entry_count(),
            queue_size_after_optional=logging_module._log_write_queue.qsize(),
            same_writer=writer is logging_module._log_writer_thread,
            writer=_writer_data(), fatal_thread=dict(_fatal_thread),
            calls=rig._call_data(), marker=marker._data(), physical_events=_events(path),
        )
        return observation
    finally:
        rig._release_all()
        if frontier is not None:
            _finish_thread(frontier[0], frontier[1], "fatal-frontier-cleanup")


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2:
        raise SystemExit("usage: log_frontier_probe.py SCENARIO ROOT")
    scenario, raw_root = arguments
    root = Path(raw_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    handlers = {
        "unprepared-reuse": _unprepared_reuse,
        "loop-refusal": _loop_refusal,
        "optional-oserror": _optional_oserror,
        "full-queue-cutoff": _full_queue_cutoff,
        "fatal-before-admission": lambda value: _fatal_writer(value, "before-admission"),
        "fatal-after-admission": lambda value: _fatal_writer(value, "after-admission"),
    }
    if scenario not in handlers:
        raise SystemExit(f"unknown scenario: {scenario}")
    persisted = write_payload_with_diff_ledger(root / "probe-report.json", handlers[scenario](root))
    print(json.dumps(persisted, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
