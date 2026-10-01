"""Integration: fatal native API event handlers settle at the public caller boundary."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from tests.integration.test_failure_diagnostic_refusals import _assert_child_origins, _selected_pythonpath

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
WORKER = Path(__file__).resolve().parents[2] / "tests/helpers/native_fatal_publication_worker.py"


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
@pytest.mark.parametrize("fatal", ["SystemExit", "KeyboardInterrupt"])
async def test_api_event_native_fatal_failure_settles_without_inner_task_escape(tmp_path, fatal, stop, record_property):
    temporary = tmp_path / "temp"
    await asyncio.to_thread(temporary.mkdir)
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONDONTWRITEBYTECODE="1",
        TMP=str(temporary), TEMP=str(temporary), PYTHONPATH=await asyncio.to_thread(_selected_pythonpath))
    process = await asyncio.create_subprocess_exec(sys.executable, str(WORKER), str(tmp_path), fatal, stop,
        cwd=tmp_path, env=environment, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    emergency_kill = False
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), 25)
        record_property("child_exit", process.returncode)
        assert process.returncode == 0, (stdout.decode(errors="replace"), stderr.decode(errors="replace"))
        data = json.loads(await asyncio.to_thread((tmp_path / "result.json").read_text, encoding="utf-8"))
        await asyncio.to_thread(_assert_child_origins, data)
        assert data["fatal_type"] == fatal and data["stop"] == stop
        assert data["failure_identity"] and data["cause_identity"] and data["context_identity"]
        assert data["failure_type"] == fatal and data["caller_cancel_requests"] == {"none": 0, "cancel": 2, "timeout": 1}[stop]
        assert data["handler_calls"] == 1 and data["native_thread"] and data["native_finished"]
        assert not data["watchdog_expired"] and data["sqlite_closed_before_emergency"] and data["sibling_continued"]
        assert data["recovery_event_written"] and not data["failed_event_written"]
        cleanup, = [item["value"] for item in data["observations"] if item["name"] == "fixture_cleanup"]
        assert cleanup == {"sqlite_closed": True, "native_finished": True}
        record_property("fatal_publication", json.dumps(data))
    finally:
        if process.returncode is None:
            emergency_kill = True
            process.kill()
        await process.wait()
        record_property("child_cleanup", json.dumps({"reaped": process.returncode is not None,
                                                      "emergency_kill": emergency_kill}))
        assert process.returncode is not None and not emergency_kill
