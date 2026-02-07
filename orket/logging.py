import json
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

def _log_path(workspace: Path, role: str = None) -> Path:
    if role:
        agent_dir = workspace / "agents"
        agent_dir.mkdir(parents=True, exist_ok=True)
        return agent_dir / f"{role}.log"
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace / "orket.log"


def log_event(event: str, data: Dict[str, Any], workspace: Path, role: str = None) -> None:
    record = {
        "timestamp": datetime.now().isoformat() + "Z",
        "role": role or data.get("role"), 
        "event": event,
        "data": data,
    }
    
    # 1. Write to main log
    main_path = _log_path(workspace)
    with main_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
        
    # 2. Write to agent-specific log if role is known
    current_role = record["role"]
    if current_role:
        agent_path = _log_path(workspace, current_role)
        with agent_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 3. Notify subscribers (for WebSockets)
    for subscriber in _subscribers:
        try:
            subscriber(record)
        except:
            pass # Prevent one bad subscriber from breaking the engine


def log_model_selected(role: str, model: str, temperature: float, seed, flow: str, workspace: Path) -> None:
    log_event(
        "model_selected",
        {
            "role": role,
            "model": model,
            "temperature": temperature,
            "seed": seed,
            "flow": flow,
        },
        workspace=workspace,
    )


def log_model_usage(role: str, model: str, tokens: Dict[str, Any], step_index: int, flow: str, workspace: Path) -> None:
    log_event(
        "model_usage",
        {
            "role": role,
            "model": model,
            "flow": flow,
            "step_index": step_index,
            "input_tokens": tokens.get("input_tokens"),
            "output_tokens": tokens.get("output_tokens"),
            "total_tokens": tokens.get("total_tokens"),
        },
        workspace=workspace,
    )