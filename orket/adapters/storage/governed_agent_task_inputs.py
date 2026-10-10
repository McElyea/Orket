"""Bounded native observation of operator-authored task files."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = False


def read_agent_task_json(path: Path) -> Any:
    require_sync_context(code="E_AGENT_TASK_INPUT_REQUIRES_NATIVE_OWNER")
    with path.open("rb") as stream:
        encoded = stream.read(1_048_577)
    if len(encoded) > 1_048_576:
        raise ValueError("E_AGENT_TASK_INPUT_BYTES_EXCEEDED")
    try:
        return json.loads(encoded)
    except RecursionError as exc:
        raise ValueError("E_AGENT_TASK_INPUT_NESTING_EXCEEDED") from exc
