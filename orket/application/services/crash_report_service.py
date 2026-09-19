"""Application authority for captured, verified fatal-error diagnostics."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from orket.adapters.storage.crash_log_store import CrashLogStore
from orket.time_utils import utc_now_datetime


@dataclass(frozen=True)
class CrashReportService:
    workspace: Path
    clock: Callable[[], datetime] = field(default=utc_now_datetime, repr=False)

    def __post_init__(self) -> None:
        if not self.workspace.is_absolute():
            raise ValueError("E_CRASH_WORKSPACE_ABSOLUTE_REQUIRED")

    async def publish(self, exception: Exception, traceback_text: str) -> Path:
        occurred_at = self.clock()
        if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
            raise ValueError("E_CRASH_TIMESTAMP_ZONE_REQUIRED")
        content = f"{occurred_at.isoformat()} - ERROR - CRITICAL CRASH: {type(exception).__name__}\n{traceback_text}\n"
        return await CrashLogStore(self.workspace).append(content)
