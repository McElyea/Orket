import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _log_path(workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace / "orket.log"


def log_event(event: str, data: Dict[str, Any], workspace: Path) -> None:
    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": event,
        "data": data,
    }
    path = _log_path(workspace)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
