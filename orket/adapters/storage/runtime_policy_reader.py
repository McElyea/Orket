"""Read-only readiness-report observation under a native or owned-worker caller."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = False


def read_runtime_policy_document(path: Path) -> dict[str, Any]:
    require_sync_context(code="E_RUNTIME_POLICY_REQUIRES_ASYNC_OWNER")
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}
