"""Observe a selected policy file inside an application-owned native operation."""

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = False  # Reads one selected document; no write, fallback or cache.


def read_outbound_policy(path: Path) -> dict[str, Any]:
    require_sync_context(code="E_OUTBOUND_POLICY_REQUIRES_ASYNC_OWNER")
    if not isinstance(path, Path) or not path.is_absolute():
        raise ValueError("E_OUTBOUND_POLICY_ABSOLUTE_PATH_REQUIRED")
    payload = json.loads(path.read_bytes().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("outbound policy config file must contain a JSON object")
    return payload
