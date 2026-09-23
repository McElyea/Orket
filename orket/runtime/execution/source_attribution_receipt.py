"""Retain one source-receipt filesystem observation through caller interruption."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_file_tools import capture_file_roots


async def observe_source_receipt(path: Path) -> tuple[bool, Any, bool]:
    """Return existence, decoded value and parse/read failure without conflating JSON null."""
    path, = capture_file_roots([path])

    def observe() -> tuple[bool, Any, bool]:
        if not path.exists():
            return False, None, False
        try:
            return True, json.loads(path.read_text(encoding="utf-8")), False
        except (OSError, ValueError, TypeError):
            return True, None, True

    return await run_owned_thread(observe, label="source-attribution-receipt")
