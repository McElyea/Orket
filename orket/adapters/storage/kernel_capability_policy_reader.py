"""Read one selected policy document; the application owns the native worker."""

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context

side_effecting = False  # Reads a selected file; does not write or cache policy state.


def read_kernel_capability_policy(path: Path) -> Any:
    require_sync_context(code="E_KERNEL_POLICY_REQUIRES_ASYNC_OWNER")
    return json.loads(path.read_bytes())
