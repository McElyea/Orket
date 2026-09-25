"""Owned child probe for audit close and fatal log-settlement precedence."""
from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType
from typing import Any

import psutil

import orket.core.runtime_event as runtime_event_module
import orket.extensions.runtime as extension_runtime_module
import orket.logging as logging_module
from orket.extensions.runtime import ExtensionEngineAdapter
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from scripts.security import build_tool_gate_audit as audit_module

WAIT_SECONDS = 5
CLOSE_MESSAGE = "controlled audit engine close failure"
FATAL_MESSAGE = "controlled fatal log writer failure"
AMBIENT_MESSAGE = "controlled ambient caller error"
PRIOR_CAUSE_MESSAGE = "controlled prior close cause"
PRIOR_CONTEXT_MESSAGE = "controlled prior close context"
PRIOR_NOTE_MESSAGE = "controlled pre-existing close note"


def _error_basic(exc: BaseException | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    message = str(exc)
    code = message.partition(":")[0] if message.startswith("E_") and ":" in message else None
    return {"type": type(exc).__name__, "message": message, "code": code}


def _error_data(exc: BaseException | None) -> dict[str, Any] | None:
    if exc is None:
        return None
    basic = _error_basic(exc)
    assert basic is not None
    return {
        **basic,
        "notes": list(getattr(exc, "__notes__", ())),
        "suppress_context": bool(exc.__suppress_context__),
        "cause": _error_basic(exc.__cause__),
        "context": _error_basic(exc.__context__),
    }


def _thread_data(thread: threading.Thread | None) -> dict[str, Any] | None:
    if thread is None:
        return None
    return {
        "name": thread.name,
        "ident": thread.ident,
        "native_id": thread.native_id,
        "daemon": thread.daemon,
        "alive": thread.is_alive(),
    }


def _contains_traceback(exc: BaseException, expected: TracebackType | None) -> bool:
    cursor = exc.__traceback__
    while cursor is not None:
        if cursor is expected:
            return True
        cursor = cursor.tb_next
    return False


@dataclass
class _Probe:
    sequence: list[str] = field(default_factory=list)
    fatal_reached: threading.Event = field(default_factory=threading.Event)
    temp_root: Path | None = None
    owner_exit_entered: bool = False
    owner_exit_exception: dict[str, Any] | None = None
    cleanup_finished: bool = False
    close_delegated: bool = False
    close_failure_raised: bool = False
    close_exception: OSError | None = None
    close_graph_before: dict[str, Any] | None = None
    close_traceback: TracebackType | None = None
    outward_is_close_exception: bool = False
    outward_contains_close_traceback: bool = False
    fatal_append_calls: int = 0
    fatal_exception: ValueError | None = None
    fatal_thread: threading.Thread | None = None
    fatal_thread_error: dict[str, Any] | None = None
    settlement_calls: int = 0
    settlement_inside_temp_owner: bool = False
    settlement_entry_exception: dict[str, Any] | None = None
    settlement_error: dict[str, Any] | None = None
    settlement_cause_is_writer_failure: bool = False
    ambient_error: dict[str, Any] | None = None


class _ObservedTemporaryDirectory:
    def __init__(self, owner: tempfile.TemporaryDirectory[str], probe: _Probe) -> None:
        self._owner = owner
        self._probe = probe

    def __enter__(self) -> str:
        path = self._owner.__enter__()
        self._probe.temp_root = Path(path)
        return path

    def __exit__(self, exc_type: Any, exc: BaseException | None, traceback: Any) -> bool | None:
        self._probe.owner_exit_entered = True
        self._probe.owner_exit_exception = _error_data(exc)
        self._probe.sequence.append("owner-exit")
        try:
            return self._owner.__exit__(exc_type, exc, traceback)
        finally:
            self._probe.cleanup_finished = True


def _install_temp_owner(probe: _Probe, root: Path) -> None:
    original = audit_module.tempfile.TemporaryDirectory

    def observed(*args: Any, **options: Any) -> _ObservedTemporaryDirectory:
        if "dir" in options:
            raise AssertionError("Audit unexpectedly supplied a temporary-directory owner root")
        return _ObservedTemporaryDirectory(original(*args, dir=root, **options), probe)

    audit_module.tempfile.TemporaryDirectory = observed


def _install_fatal_append(probe: _Probe) -> None:
    original = logging_module._append_line_sync

    def fatal_append(path: Path, line: str) -> None:
        target = None
        if probe.temp_root is not None:
            target = probe.temp_root / "workspace" / "agent_output" / "observability" / "runtime_events.jsonl"
        if target is not None and path == target and json.loads(line).get("event") == "turn_failed":
            probe.fatal_append_calls += 1
            if probe.fatal_append_calls == 3:
                failure = ValueError(FATAL_MESSAGE)
                probe.fatal_exception = failure
                probe.fatal_thread = threading.current_thread()
                probe.sequence.append("fatal-append")
                probe.fatal_reached.set()
                raise failure
        original(path, line)

    logging_module._append_line_sync = fatal_append


def _raise_close_failure(probe: _Probe) -> None:
    primary = OSError(CLOSE_MESSAGE)
    primary.add_note(PRIOR_NOTE_MESSAGE)
    try:
        try:
            raise LookupError(PRIOR_CONTEXT_MESSAGE)
        except LookupError:
            raise primary from EOFError(PRIOR_CAUSE_MESSAGE)
    except OSError as prepared:
        probe.close_exception = prepared
        probe.close_graph_before = _error_data(prepared)
        probe.close_traceback = prepared.__traceback__
        raise


def _install_close_observer(probe: _Probe, *, fail: bool) -> None:
    original = ExtensionEngineAdapter.close

    async def observed(self: ExtensionEngineAdapter) -> None:
        await original(self)
        probe.close_delegated = True
        probe.sequence.append("close-complete")
        if not fail:
            return
        reached = await asyncio.to_thread(probe.fatal_reached.wait, WAIT_SECONDS)
        if not reached:
            raise AssertionError("Fatal runtime-event append was not reached before engine close")
        probe.close_failure_raised = True
        probe.sequence.append("close-failure")
        _raise_close_failure(probe)

    ExtensionEngineAdapter.close = observed


def _install_settlement_observer(probe: _Probe) -> None:
    original = audit_module.settle_log_write_frontier

    def observed() -> None:
        probe.settlement_calls += 1
        probe.settlement_inside_temp_owner = bool(
            probe.temp_root is not None and probe.temp_root.exists() and not probe.owner_exit_entered
        )
        probe.settlement_entry_exception = _error_data(sys.exception())
        probe.sequence.append("settlement-enter")
        try:
            original()
        except BaseException as exc:
            probe.settlement_error = _error_data(exc)
            probe.settlement_cause_is_writer_failure = exc.__cause__ is logging_module._log_writer_failure
            probe.sequence.append("settlement-error")
            raise
        finally:
            probe.sequence.append("settlement-exit")

    audit_module.settle_log_write_frontier = observed


def _install_thread_observer(probe: _Probe) -> Any:
    original = threading.excepthook

    def observed(args: threading.ExceptHookArgs) -> None:
        if args.thread.name == "orket-log-writer":
            probe.fatal_thread_error = _error_basic(args.exc_value)

    threading.excepthook = observed
    return original


def _call_audit(output: Path, probe: _Probe) -> tuple[int | None, dict[str, Any] | None]:
    try:
        return audit_module.main(["--out", str(output), "--strict"]), None
    except BaseException as exc:
        probe.outward_is_close_exception = exc is probe.close_exception
        probe.outward_contains_close_traceback = _contains_traceback(exc, probe.close_traceback)
        return None, _error_data(exc)


def _invoke_audit(output: Path, scenario: str, probe: _Probe) -> tuple[int | None, dict[str, Any] | None, str]:
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        if scenario == "ambient-healthy":
            try:
                raise LookupError(AMBIENT_MESSAGE)
            except LookupError as exc:
                probe.ambient_error = _error_data(exc)
                exit_code, outward = _call_audit(output, probe)
        else:
            exit_code, outward = _call_audit(output, probe)
    return exit_code, outward, captured.getvalue()


def _capture_settlement() -> dict[str, Any]:
    try:
        logging_module.settle_log_write_frontier()
    except BaseException as exc:
        return {"status": "error", "error": _error_data(exc)}
    return {"status": "settled", "error": None}


def _build_report(
    root: Path,
    output: Path,
    scenario: str,
    probe: _Probe,
    execution: dict[str, Any],
    writer_after_audit: threading.Thread | None,
    second_settlement: dict[str, Any],
    writer_after_second: threading.Thread | None,
) -> dict[str, Any]:
    writer_failure = logging_module._log_writer_failure
    report_path = root / "probe-report.json"
    return {
        "schema_version": "audit_double_failure_probe.v1",
        "scenario": scenario,
        "process_identity": {"pid": os.getpid(), "create_time": psutil.Process().create_time()},
        "origins": {
            "logging": str(Path(logging_module.__file__).resolve()),
            "runtime_event": str(Path(runtime_event_module.__file__).resolve()),
            "extension_runtime": str(Path(extension_runtime_module.__file__).resolve()),
            "audit": str(Path(audit_module.__file__).resolve()),
            "helper": str(Path(__file__).resolve()),
        },
        "exported_writer_error": getattr(logging_module, "LOG_WRITER_TERMINATED_ERROR", None),
        "report_path": str(report_path),
        "output_path": str(output),
        "outward": execution["outward"],
        "outward_is_close_exception": probe.outward_is_close_exception,
        "outward_contains_close_traceback": probe.outward_contains_close_traceback,
        "audit_exit_code": execution["audit_exit_code"],
        "audit_stdout": execution["audit_stdout"],
        "ambient_error": probe.ambient_error,
        "close": {
            "delegated": probe.close_delegated,
            "failure_raised": probe.close_failure_raised,
            "graph_before": probe.close_graph_before,
        },
        "settlement": {
            "calls": probe.settlement_calls,
            "inside_temp_owner": probe.settlement_inside_temp_owner,
            "entry_exception": probe.settlement_entry_exception,
            "error": probe.settlement_error,
            "cause_is_writer_failure": probe.settlement_cause_is_writer_failure,
        },
        "temp_owner": {
            "root": None if probe.temp_root is None else str(probe.temp_root),
            "exit_entered": probe.owner_exit_entered,
            "exit_exception": probe.owner_exit_exception,
            "cleanup_finished": probe.cleanup_finished,
            "temp_absent": bool(probe.temp_root is not None and not probe.temp_root.exists()),
        },
        "fatal_append": {
            "calls": probe.fatal_append_calls,
            "reached": probe.fatal_reached.is_set(),
            "thread": _thread_data(probe.fatal_thread),
            "thread_error": probe.fatal_thread_error,
        },
        "writer_failure": _error_basic(writer_failure),
        "writer_failure_is_fatal": writer_failure is probe.fatal_exception,
        "writer_after_audit": _thread_data(writer_after_audit),
        "same_writer_after_audit": writer_after_audit is probe.fatal_thread,
        "second_settlement": second_settlement,
        "same_writer_after_second": writer_after_second is probe.fatal_thread,
        "output_present": output.exists(),
        "sequence": probe.sequence,
    }


def _run(root: Path, scenario: str) -> dict[str, Any]:
    probe = _Probe()
    output = root / "audit-output.json"
    _install_temp_owner(probe, root)
    _install_fatal_append(probe)
    _install_close_observer(probe, fail=scenario == "combined-close")
    _install_settlement_observer(probe)
    original_hook = _install_thread_observer(probe)
    try:
        audit_exit_code, outward, audit_stdout = _invoke_audit(output, scenario, probe)
        writer = logging_module._log_writer_thread
        if writer is not None:
            writer.join(WAIT_SECONDS)
    finally:
        threading.excepthook = original_hook
    writer_after_audit = logging_module._log_writer_thread
    second_settlement = _capture_settlement()
    writer_after_second = logging_module._log_writer_thread
    execution = {
        "audit_exit_code": audit_exit_code,
        "outward": outward,
        "audit_stdout": audit_stdout,
    }
    return _build_report(
        root, output, scenario, probe, execution,
        writer_after_audit, second_settlement, writer_after_second,
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2 or arguments[0] not in {"combined-close", "ambient-healthy"}:
        raise SystemExit("usage: audit_double_failure_probe.py <combined-close|ambient-healthy> <scenario-root>")
    scenario, raw_root = arguments
    root = Path(raw_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    report = write_payload_with_diff_ledger(root / "probe-report.json", _run(root, scenario))
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
