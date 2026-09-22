"""Layer: integration. Real request sequencing, pipes, captured inputs and output limits."""
import asyncio
import os
import sys
from pathlib import Path

import psutil
import pytest

from orket.adapters.execution.openclaw_jsonl_adapter import OpenClawJsonlSubprocessAdapter
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.core.contracts.owned_command import CommandExecutionUncertain
from tests.integration.test_provider_governance_command_lifetime import (
    _assert_receipt,
)
from tests.integration.test_provider_governance_command_lifetime import (
    command_receipts as command_receipts,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FIXTURE = Path(__file__).with_name("openclaw_exchange_worker.py")


def adapter(root, mode, *, environment=None, runner=None):
    return OpenClawJsonlSubprocessAdapter(command=[sys.executable, str(FIXTURE), mode, str(root)],
        runner=runner or CommandProcessSupervisor(root, cancellation_event="openclaw_fixture_interrupted"),
        cwd=root, env=environment, io_timeout_seconds=1)


async def _await_file(path):
    async with asyncio.timeout(5):
        # This marker belongs to another process; retain the five-second admission bound.
        for _ in range(500):
            if await asyncio.to_thread(path.exists):
                return
            await asyncio.sleep(0.01)
    raise AssertionError("Fixture did not publish its admission marker")


async def test_next_request_waits_for_previous_response(tmp_path, command_receipts):
    task = asyncio.create_task(adapter(tmp_path, "sequence").run_requests([{"index": 0}, {"index": 1}]))
    try:
        await _await_file(tmp_path / "first-read")
        await asyncio.sleep(0.08)
        assert not await asyncio.to_thread((tmp_path / "request-1.json").exists)
        await asyncio.to_thread((tmp_path / "release-response").touch)
        result = await asyncio.wait_for(asyncio.shield(task), 5)
        assert result.ok and [row["request"]["index"] for row in result.responses] == [0, 1]
        assert (await _assert_receipt(command_receipts)).reason == "completed"
    finally:
        await asyncio.to_thread((tmp_path / "release-response").touch)
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)


@pytest.mark.parametrize("mode", ["invalid-json", "non-object", "invalid-utf8", "line-limit", "deep-json"])
async def test_invalid_response_preserves_only_accepted_prefix(tmp_path, command_receipts, mode):
    result = await adapter(tmp_path, mode).run_requests([{"index": 0}, {"index": 1}, {"index": 2}])
    count = 0 if mode == "line-limit" else 1
    assert not result.ok and result.completed_count == result.failed_at == count
    assert [row["request"]["index"] for row in result.responses] == list(range(count))
    assert not await asyncio.to_thread((tmp_path / f"request-{count + 1}.json").exists)
    receipt = await _assert_receipt(command_receipts)
    assert receipt.reason == "protocol_failed"
    expected = {"line-limit": "jsonl_response_line_limit", "non-object": "jsonl_response_not_object"}.get(
        mode, "jsonl_response_invalid_json")
    assert expected in receipt.diagnostics


@pytest.mark.parametrize("mode,requests", [("stderr-pressure", [{"index": 0}]), ("no-newline", [{"index": 0}]),
                                           ("normal", [])])
async def test_real_stream_completion_preserves_protocol(tmp_path, command_receipts, mode, requests):
    result = await adapter(tmp_path, mode).run_requests(requests)
    assert result.ok and result.completed_count == len(requests)
    assert [row["request"] for row in result.responses] == requests
    receipt = await _assert_receipt(command_receipts)
    assert receipt.reason == "completed"
    if mode == "stderr-pressure":
        assert receipt.stderr == b"e" * (512 * 1024)


async def test_blocked_request_write_has_its_own_deadline(tmp_path, command_receipts):
    result = await asyncio.wait_for(adapter(tmp_path, "blocked-write").run_requests([{"payload": "x" * (2 * 1024 * 1024)}]), 10)
    assert not result.ok and result.completed_count == result.failed_at == 0
    receipt = await _assert_receipt(command_receipts)
    assert receipt.reason == "timeout" and "jsonl_timeout:write" in receipt.diagnostics


async def test_actual_stderr_overflow_refuses_partial_capture(tmp_path, command_receipts):
    with pytest.raises(CommandExecutionUncertain) as failure:
        await adapter(tmp_path, "stderr-limit").run_requests([{"index": 0}])
    receipt, = command_receipts
    assert failure.value.lifetime is receipt
    assert receipt.cleanup_confirmed and not receipt.capture_complete and receipt.reason == "output_limit"
    for pid in (receipt.supervisor_pid, receipt.transport_pid):
        assert not await asyncio.to_thread(psutil.pid_exists, pid)


async def test_missing_native_command_is_partial_failure_after_confirmed_cleanup(tmp_path, command_receipts):
    instance = adapter(tmp_path, "normal")
    instance.command = (str(tmp_path / "missing-executable"),)
    result = await instance.run_requests([{}])
    assert not result.ok and result.completed_count == result.failed_at == 0
    receipt, = command_receipts
    assert receipt.cleanup_confirmed and receipt.reason == "launch_failed"
    for pid in (receipt.supervisor_pid, receipt.transport_pid):
        assert not await asyncio.to_thread(psutil.pid_exists, pid)


async def test_dispatch_captures_nested_requests_environment_directory_and_command(tmp_path, monkeypatch, command_receipts):
    entered, release = asyncio.Event(), asyncio.Event()
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="openclaw_fixture_interrupted")

    class HeldRunner:
        async def run_jsonl(self, *args, **kwargs):
            entered.set()
            await release.wait()
            return await owner.run_jsonl(*args, **kwargs)

    environment = dict(os.environ, ORKET_JSONL_FIXTURE="captured")
    request = [{"nested": {"value": "captured"}}]
    instance = adapter(tmp_path, "normal", environment=environment, runner=HeldRunner())
    task = asyncio.create_task(instance.run_requests(request))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        request[0]["nested"]["value"] = "changed"
        instance.env["ORKET_JSONL_FIXTURE"] = "changed"
        instance.command = ("missing-after-dispatch",)
        instance.cwd = str(tmp_path.parent)
        monkeypatch.chdir(tmp_path.parent)
        release.set()
        result = await asyncio.wait_for(asyncio.shield(task), 5)
        assert result.ok and result.responses == [{"request": {"nested": {"value": "captured"}},
                                                   "cwd": str(tmp_path), "environment": "captured"}]
        await _assert_receipt(command_receipts)
    finally:
        release.set()
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 5)
