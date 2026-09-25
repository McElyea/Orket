import asyncio
import contextlib
import json
import logging
import os
import queue
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypedDict

from orket.core.runtime_event import (
    RUNTIME_EVENT_ARTIFACT_EVENTS,
    _build_runtime_event,
)
from orket.core.runtime_event import (
    RUNTIME_EVENT_SCHEMA_VERSION as RUNTIME_EVENT_SCHEMA_VERSION,
)
from orket.naming import sanitize_name
from orket.time_utils import now_local

# Initialize system logger
_logger = logging.getLogger("orket")
_logger.setLevel(logging.INFO)

_LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warn": logging.WARNING,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}
_prepared_log_dirs: set[Path] = set()
_prepared_log_dirs_lock = threading.Lock()
LOG_QUEUE_MAX_ENV = "ORKET_LOG_QUEUE_MAX"
DEFAULT_LOG_QUEUE_MAX = 10_000
LOG_WRITER_TERMINATED_ERROR = "E_LOG_WRITER_TERMINATED: log writer stopped before the requested frontier"


side_effecting = True


def _resolve_log_queue_max() -> int:
    try:
        configured = int(str(os.getenv(LOG_QUEUE_MAX_ENV, "")).strip())
    except ValueError:
        return DEFAULT_LOG_QUEUE_MAX
    return configured if configured > 0 else DEFAULT_LOG_QUEUE_MAX


class _LogWriteFrontier:
    def __init__(self) -> None:
        self.settled = False


_LogWriteItem = tuple[Path, str] | _LogWriteFrontier
_log_write_queue: queue.Queue[_LogWriteItem] = queue.Queue(maxsize=_resolve_log_queue_max())
_log_writer_lock = threading.Lock()
_log_writer_state = threading.Condition()
_log_writer_thread: threading.Thread | None = None
_log_writer_failure: BaseException | None = None
_dropped_log_entries = 0
_dropped_log_entries_lock = threading.Lock()


class _MemberMetrics(TypedDict):
    tokens: int
    lines_written: int
    last_action: str
    detail: str


def _record_log_writer_failure(failure: BaseException) -> None:
    global _log_writer_failure
    with _log_writer_state:
        if _log_writer_failure is None:
            _log_writer_failure = failure
        _log_writer_state.notify_all()


def _require_log_writer_alive() -> None:
    writer = _log_writer_thread
    if _log_writer_failure is None and writer is not None and writer.is_alive():
        return
    raise RuntimeError(LOG_WRITER_TERMINATED_ERROR) from _log_writer_failure


def _start_log_writer() -> None:
    global _log_writer_thread
    with _log_writer_lock:
        if _log_writer_thread is not None:
            return
        thread = threading.Thread(target=_log_writer_loop, name="orket-log-writer", daemon=True)
        with _log_writer_state:
            _log_writer_thread = thread
        try:
            thread.start()
        except RuntimeError as exc:  # preserve process interrupts while recording thread-start failure
            _record_log_writer_failure(exc)
            _require_log_writer_alive()


def _log_writer_loop() -> None:
    try:
        while True:
            item = _log_write_queue.get()
            with _log_writer_state:
                _log_writer_state.notify_all()  # a full queue now has one available slot
            frontier = item if isinstance(item, _LogWriteFrontier) else None
            try:
                if frontier is None:
                    path, line = item
                    _append_line_sync(path, line)
            except OSError:
                pass
            finally:
                _log_write_queue.task_done()
                if frontier is not None:
                    with _log_writer_state:
                        frontier.settled = True
                        _log_writer_state.notify_all()
    except BaseException as exc:  # daemon supervisor boundary must not strand a frontier waiter
        _record_log_writer_failure(exc)
        raise


def settle_log_write_frontier() -> None:
    """Block natively until prior accepted optional appends have settled."""
    if _running_on_event_loop():
        raise RuntimeError("E_LOG_WRITE_FRONTIER_REQUIRES_NATIVE_CONTEXT: settlement blocks the calling thread")
    _start_log_writer()
    frontier = _LogWriteFrontier()
    with _log_writer_state:
        while True:
            _require_log_writer_alive()
            try:
                _log_write_queue.put_nowait(frontier)
            except queue.Full:
                _log_writer_state.wait()
            else:
                break
        while not frontier.settled:
            _require_log_writer_alive()
            _log_writer_state.wait()


def dropped_log_entry_count() -> int:
    with _dropped_log_entries_lock:
        return _dropped_log_entries


def _record_dropped_log_entry(path: Path) -> None:
    global _dropped_log_entries
    with _dropped_log_entries_lock:
        _dropped_log_entries += 1
        dropped = _dropped_log_entries
    if dropped == 1 or dropped % 1000 == 0:
        _logger.warning(
            "log_write_queue_full",
            extra={
                "orket_record": {
                    "event": "log_write_queue_full",
                    "data": {
                        "dropped_log_entries": dropped,
                        "queue_max": _log_write_queue.maxsize,
                        "path": str(path),
                    },
                }
            },
        )


def _append_line_sync(path: Path, line: str) -> None:
    _ensure_log_parent(path)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _ensure_log_parent(path: Path) -> None:
    directory = path.parent.resolve()
    with _prepared_log_dirs_lock:
        if directory in _prepared_log_dirs:
            return
        directory.mkdir(parents=True, exist_ok=True)
        _prepared_log_dirs.add(directory)


def _running_on_event_loop() -> bool:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return False
    return True


def _append_json_record(path: Path, payload: dict[str, Any]) -> None:
    line = json.dumps(payload, ensure_ascii=False, default=str) + "\n"
    if _running_on_event_loop():
        _start_log_writer()
        try:
            _log_write_queue.put_nowait((path, line))
        except queue.Full:
            _record_dropped_log_entry(path)
        return
    _append_line_sync(path, line)


def _resolve_level_name(level: Any) -> str:
    token = str(level or "").strip().lower()
    if token in _LOG_LEVELS:
        return "warning" if token == "warn" else token
    return "info"


def _emit_stdlib_record(level_name: str, event: str, record: dict[str, Any]) -> None:
    _logger.log(_LOG_LEVELS[level_name], str(event or "").strip(), extra={"orket_record": record})


def setup_logging(workspace: Path) -> Path:
    """Ensures workspace log directory exists and returns the target log file."""
    path = workspace / "orket.log"
    _ensure_log_parent(path)
    return path


# Global list of event subscribers (e.g. for WebSockets)
_subscribers: list[Callable[[dict[str, Any]], None]] = []

MISSING_WORKSPACE_MODE_ENV = "ORKET_LOGGING_MISSING_CONTEXT_MODE"
MISSING_WORKSPACE_MODE_LEGACY = "legacy_default"
MISSING_WORKSPACE_MODE_FAIL_FAST = "fail_fast"
MISSING_WORKSPACE_ERROR_CODE = "E_LOG_WORKSPACE_REQUIRED"


def subscribe_to_events(callback: Callable[[dict[str, Any]], None]) -> None:
    if callback not in _subscribers:
        _subscribers.append(callback)


def unsubscribe_from_events(callback: Callable[[dict[str, Any]], None]) -> None:
    if callback in _subscribers:
        _subscribers.remove(callback)


def event_subscriber_count() -> int:
    return len(_subscribers)


def _resolve_missing_workspace_mode() -> str:
    raw = str(os.getenv(MISSING_WORKSPACE_MODE_ENV, "")).strip().lower()
    if raw == MISSING_WORKSPACE_MODE_FAIL_FAST:
        return MISSING_WORKSPACE_MODE_FAIL_FAST
    return MISSING_WORKSPACE_MODE_LEGACY


def _resolve_workspace(workspace: Path | None) -> tuple[Path, dict[str, Any]]:
    if workspace is not None:
        return workspace, {}
    mode = _resolve_missing_workspace_mode()
    if mode == MISSING_WORKSPACE_MODE_FAIL_FAST:
        raise RuntimeError(
            f"{MISSING_WORKSPACE_ERROR_CODE}: log_event requires workspace when "
            f"{MISSING_WORKSPACE_MODE_ENV}={MISSING_WORKSPACE_MODE_FAIL_FAST}"
        )
    return (
        Path("workspace/default"),
        {
            "logging_context_mode": MISSING_WORKSPACE_MODE_LEGACY,
            "logging_context_marker": "workspace_default_fallback",
        },
    )


def _log_path(workspace: Path, role: str | None = None) -> Path:
    root_log = Path("workspace/default/orket.log")
    root_log.parent.mkdir(parents=True, exist_ok=True)
    if role:
        agent_dir = workspace / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        # Sanitize name for filename consistency
        safe_name = sanitize_name(role)
        return agent_dir / f"{safe_name}.log"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace / "orket.log"


def _append_runtime_event_artifact(workspace: Path, runtime_event: dict[str, Any]) -> None:
    session_id = str(runtime_event.get("session_id") or "").strip()
    if not session_id:
        return
    event_name = str(runtime_event.get("event") or "").strip()
    if event_name not in RUNTIME_EVENT_ARTIFACT_EVENTS:
        return
    path = workspace / "agent_output" / "observability" / "runtime_events.jsonl"
    _append_json_record(path, runtime_event)


def log_event(
    event: str,
    data: dict[str, Any] | None = None,
    workspace: Path | None = None,
    role: str | None = None,
    **kwargs: Any,
) -> None:
    """
    Unified log router.
    Supports:
    - log_event("event_name", data_dict, workspace, role="X")
    - log_event("event_name", data_dict, workspace=workspace)
    - log_event(level, component, event, payload) [Legacy Compat]
    """
    # 1. Handle legacy signature if 'event' looks like a level and data is component-like
    if (
        event in {"debug", "info", "warn", "warning", "error", "critical"}
        and isinstance(data, str)
        and len(kwargs) == 0
    ):
        # Shift args: event -> level, data -> component, workspace -> event, role -> payload
        level = event
        component = data
        actual_event = workspace if isinstance(workspace, str) else "generic_event"
        actual_data = role if isinstance(role, dict) else {}
        # Recurse with unified signature
        return log_event(actual_event, actual_data, role=component, level=level)
    if data is None:
        data = {}
    workspace, context_marker = _resolve_workspace(workspace)
    level_name = _resolve_level_name(kwargs.pop("level", None))

    # Merge extra kwargs into data for observability
    full_data = {**data, **kwargs}
    if context_marker:
        full_data.update(context_marker)
    role_name = role or full_data.get("role") or "system"
    runtime_event = _build_runtime_event(event, full_data, role_name)
    full_data = {**full_data, "runtime_event": runtime_event}

    record = {
        "timestamp": now_local().isoformat(),
        "level": level_name,
        "role": role_name,
        "event": event,
        "data": full_data,
    }

    _emit_stdlib_record(level_name, event, record)
    log_file = setup_logging(workspace)

    # 1. Emit JSON record to this workspace only.
    _append_json_record(log_file, record)
    with contextlib.suppress(RuntimeError, ValueError, TypeError, OSError):
        _append_runtime_event_artifact(workspace, runtime_event)

    # 2. Notify subscribers (for WebSockets)
    for subscriber in _subscribers:
        try:
            subscriber(record)
        except (RuntimeError, ValueError, TypeError, OSError) as e:
            failure_record = {
                "timestamp": now_local().isoformat(),
                "level": "error",
                "role": "system",
                "event": "logging_subscriber_failed",
                "data": {"error": str(e)},
            }
            _emit_stdlib_record("error", "logging_subscriber_failed", failure_record)
            _append_json_record(log_file, failure_record)


def log_model_selected(
    role: str,
    model: str,
    temperature: float,
    seed: int | None,
    epic: str,
    workspace: Path,
) -> None:
    log_event(
        "model_selected",
        {
            "role": role,
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "epic": epic,
        },
        workspace=workspace,
    )


def log_model_usage(role: str, model: str, tokens: dict[str, Any], step_index: int, epic: str, workspace: Path) -> None:
    log_event(
        "model_usage",
        {
            "role": role,
            "model": model,
            "epic": epic,
            "step_index": step_index,
            "input_tokens": tokens.get("input_tokens"),
            "output_tokens": tokens.get("output_tokens"),
            "total_tokens": tokens.get("total_tokens"),
        },
        workspace=workspace,
    )


def get_member_metrics(workspace: Path) -> dict[str, _MemberMetrics]:
    """
    Aggregates stats per role from the workspace/orket.log.
    """
    log_path = workspace / "orket.log"
    if not log_path.exists():
        return {}

    metrics: dict[str, _MemberMetrics] = {}
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if not isinstance(record, dict):
                    continue
                role_value = record.get("role")
                if not isinstance(role_value, str) or not role_value:
                    continue
                role = role_value

                if role not in metrics:
                    metrics[role] = {"tokens": 0, "lines_written": 0, "last_action": "Idle", "detail": ""}

                event = record.get("event")
                data = record.get("data")
                data_dict = data if isinstance(data, dict) else {}

                if event == "model_usage":
                    total_tokens = data_dict.get("total_tokens")
                    if isinstance(total_tokens, int):
                        metrics[role]["tokens"] += total_tokens
                elif event == "tool_call":
                    tool = data_dict.get("tool")
                    metrics[role]["last_action"] = f"Executing {tool}"
                    if tool == "write_file":
                        args_payload = data_dict.get("args")
                        args_dict = args_payload if isinstance(args_payload, dict) else {}
                        content = args_dict.get("content")
                        content_text = content if isinstance(content, str) else ""
                        metrics[role]["lines_written"] += len(content_text.splitlines())
                        metrics[role]["detail"] = f"Wrote {args_dict.get('path')}"
                elif event == "auto_persist":
                    metrics[role]["detail"] = f"Persisted {data_dict.get('path')}"
            except (json.JSONDecodeError, KeyError):
                continue
    return metrics
