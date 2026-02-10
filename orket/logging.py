import json
import os
import logging
import logging.handlers
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Callable

# Initialize system logger
_logger = logging.getLogger("orket")
_logger.setLevel(logging.INFO)

def setup_logging(workspace: Path):
    """Configures rotating file handlers for the workspace."""
    log_file = workspace / "orket.log"
    workspace.mkdir(parents=True, exist_ok=True)
    
    # Rotating handler: 10MB per file, keep 5 backups
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5, encoding="utf-8"
    )
    # Structured JSON format for machine parsing
    formatter = logging.Formatter('%(message)s')
    handler.setFormatter(formatter)
    
    if not any(isinstance(h, logging.handlers.RotatingFileHandler) and h.baseFilename == str(log_file.resolve()) for h in _logger.handlers):
        _logger.addHandler(handler)

# Global list of event subscribers (e.g. for WebSockets)
_subscribers: List[Callable[[Dict[str, Any]], None]] = []

def subscribe_to_events(callback: Callable[[Dict[str, Any]], None]):
    _subscribers.append(callback)

def unsubscribe_from_events(callback: Callable[[Dict[str, Any]], None]):
    if callback in _subscribers:
        _subscribers.remove(callback)

from orket.naming import sanitize_name

def _log_path(workspace: Path, role: str = None) -> Path:
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


def log_event(event: str, data: Dict[str, Any] = None, workspace: Optional[Path] = None, role: str = None, **kwargs) -> None:
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

    if data is None: data = {}
    if workspace is None:
        workspace = Path("workspace/default")
    
    # Merge extra kwargs into data for observability
    full_data = {**data, **kwargs}
    
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "role": role or full_data.get("role") or "system", 
        "event": event,
        "data": full_data,
    }
    
    # 1. Ensure logging is set up for this workspace
    setup_logging(workspace)
    
    # 2. Emit JSON record
    _logger.info(json.dumps(record, ensure_ascii=False))

    # 3. Notify subscribers (for WebSockets)
    for subscriber in _subscribers:
        try:
            subscriber(record)
        except Exception as e:
            # Print to stderr but don't crash
            print(f"  [LOGGING] Subscriber failed: {e}")
            pass


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


def log_model_usage(role: str, model: str, tokens: Dict[str, Any], step_index: int, epic: str, workspace: Path) -> None:
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

def get_member_metrics(workspace: Path) -> Dict[str, Any]:
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

def log_crash(exception: Exception, traceback_str: str, workspace: Optional[Path] = None):
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