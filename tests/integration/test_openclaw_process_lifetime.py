"""Layer: integration. Actual interactive adapter trees and independent SQLite/effect observers."""
import asyncio
import json
import time

import aiosqlite
import psutil
import pytest

from tests.helpers.openclaw_lifetime import adapter_for, observe_fixture
from tests.integration.test_provider_governance_command_lifetime import (
    _assert_receipt,
)
from tests.integration.test_provider_governance_command_lifetime import (
    command_receipts as command_receipts,
)
from tests.integration.test_verification_process_lifetime import (
    assert_stopped,
    await_tree,
    stop_observed,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _responsive(root, record_property):
    started = time.perf_counter()
    async with aiosqlite.connect(root / "unrelated.sqlite3") as connection:
        assert await (await connection.execute("SELECT 42")).fetchone() == (42,)
    latency = time.perf_counter() - started
    record_property("openclaw_sqlite_seconds", latency)
    assert latency < 0.5


async def _cleanup(task, processes, root):
    processes = list(set(processes + await asyncio.to_thread(observe_fixture, root)))
    await asyncio.to_thread(stop_observed, processes)
    if not task.done():
        task.cancel()
    await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    await assert_stopped(processes, root)


@pytest.mark.parametrize("stop", ["leader-exit", "leader-failure", "cancel", "repeated-cancel", "timeout"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"], ["inherited-pipes", "detached", "ignore-term"]],
                         ids=["ordinary", "detached-resistant", "inherited-resistant"])
async def test_openclaw_settles_native_descendants(tmp_path, record_property, command_receipts, stop, flags):
    adapter = adapter_for(tmp_path, stop, flags)
    task = asyncio.create_task(adapter.run_requests([{"index": 0}]))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        marker = await asyncio.to_thread((tmp_path / "adapter-ready.json").read_text, encoding="utf-8")
        processes.append(await asyncio.to_thread(psutil.Process, json.loads(marker)["pid"]))
        await _responsive(tmp_path, record_property)
        if stop.startswith("leader-"):
            await asyncio.to_thread((tmp_path / "release-response").touch)
        if "cancel" in stop:
            task.cancel()
            if stop == "repeated-cancel":
                for _ in range(20):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(asyncio.shield(task), 10)
        else:
            result = await asyncio.wait_for(asyncio.shield(task), 10)
            assert result.ok is (stop == "leader-exit")
            assert result.responses == ([{"index": 0}] if stop.startswith("leader-") else [])
        await assert_stopped(processes, tmp_path)
        receipt = await _assert_receipt(command_receipts)
        assert receipt.reason == ("cancelled" if "cancel" in stop else "timeout" if stop == "timeout" else "completed")
    finally:
        await _cleanup(task, processes, tmp_path)
