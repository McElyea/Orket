"""Integration: actual trusted SDK children, native ownership and observed writes."""
from __future__ import annotations

import asyncio
import sys
import tempfile

import pytest

from orket.extensions.sdk_workload_runner import SdkSubprocessRunError, run_sdk_workload_in_subprocess
from tests.helpers.sdk_lifetime import owned_fixture_processes, sdk_request
from tests.integration.test_verification_process_lifetime import assert_stopped, await_tree, stop_observed

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "caller-timeout", "native-timeout", "success", "error"])
@pytest.mark.parametrize("flags", [(), ("detached", "ignore-term")], ids=["ordinary", "detached-resistant"])
async def test_sdk_owns_live_descendants_through_return(tmp_path, monkeypatch, stop, flags, caplog):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))
    options = sdk_request(tmp_path, tree=True, flags=flags, mode="error" if stop == "error" else "success")
    if stop == "native-timeout":
        options["timeout_seconds"] = 5
    task = asyncio.create_task(run_sdk_workload_in_subprocess(**options))
    processes = []
    try:
        await await_tree(tmp_path)
        processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        assert len(processes) >= 4
        if stop in {"cancel", "repeated-cancel", "caller-timeout"}:
            if stop == "caller-timeout":
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(task, .01)
            else:
                task.cancel()
                if stop == "repeated-cancel":
                    for _ in range(20):
                        if task.done():
                            break
                        await asyncio.sleep(.01)
                        task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await asyncio.wait_for(task, 5)
            event = "sdk_workload_process_cancelled"
        elif stop == "native-timeout":
            from orket.extensions.sdk_workload_runner import SdkSubprocessExecutionUncertain
            with pytest.raises(SdkSubprocessExecutionUncertain) as caught:
                await asyncio.wait_for(asyncio.shield(task), 10)
            assert caught.value.lifetime.reason == "timeout"
            assert caught.value.exchange_path.is_dir()
            event = "sdk_workload_process_observed"
        else:
            await asyncio.to_thread((tmp_path / "release-sdk").touch)
            if stop == "error":
                with pytest.raises(SdkSubprocessRunError, match="controlled workload failure"):
                    await asyncio.wait_for(asyncio.shield(task), 5)
            else:
                result = await asyncio.wait_for(asyncio.shield(task), 5)
                assert result.workload_result.ok
                assert result.workload_result.output == {"effect": "executed"}
            event = "sdk_workload_process_observed"
        await assert_stopped(processes, tmp_path)
        observations = [r.orket_record["data"] for r in caplog.records if r.message == event]
        assert len(observations) == 1
        assert observations[0]["cleanup_confirmed"] is True
        assert observations[0]["backend"] == ("windows_job" if sys.platform == "win32" else "linux_subreaper")
        assert bool(list(exchanges.iterdir())) is (stop == "native-timeout")
    finally:
        if not processes:
            processes = await asyncio.to_thread(owned_fixture_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
