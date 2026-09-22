"""Read an explicitly selected offline ledger export through an owned worker."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread

side_effecting = True


class OutwardLedgerFileStore:
    # The read observes external filesystem state; it does not mutate the ledger.
    side_effecting = True

    async def read(self, path: Path) -> Any:
        def observe() -> Any:
            return json.loads(path.read_text(encoding="utf-8"))
        return await run_owned_thread(observe, label="offline-ledger-read")
