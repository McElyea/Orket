import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Callable

# Global list of event subscribers (e.g. for WebSockets)
_subscribers: List[Callable[[Dict[str, Any]], None]] = []

def subscribe_to_events(callback: Callable[[Dict[str, Any]], None]):
    _subscribers.append(callback)

def unsubscribe_from_events(callback: Callable[[Dict[str, Any]], None]):
    if callback in _subscribers:
        _subscribers.remove(callback)

from orket.utils import sanitize_name

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


def log_event(event: str, data: Dict[str, Any], workspace: Path, role: str = None) -> None:
    record = {
        "timestamp": datetime.now().isoformat() + "Z",
        "role": role or data.get("role"), 
        "event": event,
        "data": data,
    }
    
    # 1. Write to consolidated root log (Source of Truth for UI)
    root_path = Path("workspace/default/orket.log")
    # Skip root logging if we are in a test environment or if it doesn't exist
    if not any("pytest" in arg for arg in os.sys.argv):
        root_path.parent.mkdir(parents=True, exist_ok=True)
        with root_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 2. Write to local workspace log
    main_path = workspace / "orket.log"
    if main_path != root_path:
        main_path.parent.mkdir(parents=True, exist_ok=True)
        with main_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
    # 3. Write to agent-specific log if role is known
    current_role = record["role"]
    if current_role:
        agent_path = _log_path(workspace, current_role)
        with agent_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 3. Notify subscribers (for WebSockets)
    for subscriber in _subscribers:
        try:
            subscriber(record)
        except Exception:
            pass  # Prevent one bad subscriber from breaking the engine


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
    return metrics