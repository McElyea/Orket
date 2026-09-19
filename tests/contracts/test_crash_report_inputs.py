"""Explicit crash-publication input admission before durable effects."""
import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from orket.adapters.storage.crash_log_store import CrashLogStore
from orket.application.services.crash_report_service import CrashReportService

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("owner", [CrashReportService, CrashLogStore])
def test_relative_workspace_is_refused(owner):
    with pytest.raises(ValueError, match="E_CRASH_WORKSPACE_ABSOLUTE_REQUIRED"):
        owner(Path("relative"))


@pytest.mark.parametrize("options", [{"max_bytes": 0}, {"backup_count": 0}])
def test_invalid_rotation_limits_are_refused(tmp_path, options):
    with pytest.raises(ValueError, match="E_CRASH_ROTATION_LIMIT_INVALID"):
        CrashLogStore(tmp_path, **options)
    assert not list(tmp_path.iterdir())


@pytest.mark.asyncio
async def test_naive_clock_is_refused_before_filesystem_effects(tmp_path):
    owner = CrashReportService(tmp_path, clock=lambda: datetime(2026, 9, 19))
    with pytest.raises(ValueError, match="E_CRASH_TIMESTAMP_ZONE_REQUIRED"):
        await owner.publish(ValueError(), "trace")
    assert not await asyncio.to_thread(lambda: list(tmp_path.iterdir()))


@pytest.mark.asyncio
async def test_empty_record_is_refused_before_filesystem_effects(tmp_path):
    with pytest.raises(ValueError, match="E_CRASH_RECORD_EMPTY"):
        await CrashLogStore(tmp_path).append("")
    assert not await asyncio.to_thread(lambda: list(tmp_path.iterdir()))
