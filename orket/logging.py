import asyncio
import json
import logging
import logging.handlers
import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable

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
_log_write_queue: queue.SimpleQueue[tuple[Path, str]] = queue.SimpleQueue()
_log_writer_lock = threading.Lock()
_log_writer_started = False


def _start_log_writer() -> None:
    global _log_writer_started
    if _log_writer_started:
        return
    with _log_writer_lock:
        if _log_writer_started:
            return
        thread = threading.Thread(target=_log_writer_loop, name="orket-log-writer", daemon=True)
        thread.start()
        _log_writer_started = True


def _log_writer_loop() -> None:
    while True:
        path, line = _log_write_queue.get()
        try:
            _append_line_sync(path, line)
        except OSError:
            continue


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
        _log_write_queue.put((path, line))
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

from orket.naming import sanitize_name

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


RUNTIME_EVENT_SCHEMA_VERSION = "v1"
RUNTIME_EVENT_ARTIFACT_EVENTS = {
    "packet1_emission_failure",
    "session_start",
    "session_end",
    "turn_start",
    "turn_complete",
    "turn_failed",
    "runtime_verifier_completed",
    "guard_retry_scheduled",
    "guard_terminal_failure",
}


def _build_runtime_event(event: str, data: dict[str, Any], role: str) -> dict[str, Any]:
    payload = dict(data or {})
    return {
        "schema_version": RUNTIME_EVENT_SCHEMA_VERSION,
        "event": str(event or "").strip(),
        "role": str(role or payload.get("role") or "system"),
        "session_id": str(payload.get("session_id") or ""),
        "issue_id": str(payload.get("issue_id") or ""),
        "turn_index": int(payload.get("turn_index") or 0),
        "turn_trace_id": str(payload.get("turn_trace_id") or ""),
        "selected_model": str(payload.get("selected_model") or ""),
        "prompt_id": str(payload.get("prompt_id") or ""),
        "prompt_version": str(payload.get("prompt_version") or ""),
        "prompt_checksum": str(payload.get("prompt_checksum") or ""),
        "resolver_policy": str(payload.get("resolver_policy") or ""),
        "selection_policy": str(payload.get("selection_policy") or ""),
        "guard_contract": payload.get("guard_contract"),
        "guard_decision": payload.get("guard_decision"),
        "terminal_reason": (
            (payload.get("guard_decision") or {}).get("terminal_reason")
            if isinstance(payload.get("guard_decision"), dict)
            else None
        ),
        "stage": str(payload.get("stage") or ""),
        "error_type": str(payload.get("error_type") or ""),
        "error": str(payload.get("error") or ""),
        "packet1_conformance": payload.get("packet1_conformance"),
        "duration_ms": int(payload.get("duration_ms") or 0),
        "tokens": payload.get("tokens"),
    }


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
    if event in {"debug", "info", "warn", "warning", "error", "critical"} and isinstance(data, str) and len(kwargs) == 0:
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
    try:
        _append_runtime_event_artifact(workspace, runtime_event)
    except (RuntimeError, ValueError, TypeError, OSError):
        pass

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


def log_model_selected(role: str, model: str, temperature: float, seed, epic: str, workspace: Path) -> None:
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

def get_member_metrics(workspace: Path) -> dict[str, Any]:
    """
    Aggregates stats per role from the workspace/orket.log.
    """
    log_path = workspace / "orket.log"
    if not log_path.exists():
        return {}

    metrics = {}
    with log_path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                role = record.get("role")
                if not role: continue
                
                if role not in metrics:
                    metrics[role] = {"tokens": 0, "lines_written": 0, "last_action": "Idle", "detail": ""}
                
                event = record.get("event")
                data = record.get("data", {})
                
                if event == "model_usage":
                    metrics[role]["tokens"] += (data.get("total_tokens") or 0)
                elif event == "tool_call":
                    tool = data.get("tool")
                    metrics[role]["last_action"] = f"Executing {tool}"
                    if tool == "write_file":
                        content = data.get("args", {}).get("content", "")
                        metrics[role]["lines_written"] += len(content.splitlines())
                        metrics[role]["detail"] = f"Wrote {data.get('args', {}).get('path')}"
                elif event == "auto_persist":
                    metrics[role]["detail"] = f"Persisted {data.get('path')}"
            except (json.JSONDecodeError, KeyError):
                continue
    return metrics

def log_crash(exception: Exception, traceback_str: str, workspace: Path | None = None) -> None:
    """
    Safely logs a crash to a rotating file.
    """
    if workspace is None:
        workspace = Path("workspace/default")
    
    workspace.mkdir(parents=True, exist_ok=True)
    crash_log = workspace / "orket_crash.log"
    
    # Create a dedicated logger for crashes to avoid interference with the main logger
    crash_logger = logging.getLogger("orket_crash")
    crash_logger.setLevel(logging.ERROR)
    
    if not crash_logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            crash_log, maxBytes=5*1024*1024, backupCount=5, encoding="utf-8"
        )
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        crash_logger.addHandler(handler)
    
    crash_logger.error(f"CRITICAL CRASH: {type(exception).__name__}\n{traceback_str}")
