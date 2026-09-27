"""Layer: integration. Real support-artifact publication and native ownership."""
import asyncio
import json
import threading
import time
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_verification_artifact_service import (
    RuntimeVerificationArtifactContext,
    RuntimeVerificationArtifactService,
)
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_path,
    hold_stream,
    settle,
    sqlite_response,
    timeout_while_held,
    wait_entered,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def publication(root):
    context = RuntimeVerificationArtifactContext("run", "REV-1", 1, 0, "reviewer", "2026-09-27T00:00:00Z")
    result = SimpleNamespace(ok=True, checked_files=[], errors=[], command_results=[], failure_breakdown={},
                             overall_evidence_class="syntax_only", evidence_summary={"nested": {"value": "original"}})
    guard = {"violations": [{"code": "original"}]}
    service = RuntimeVerificationArtifactService(root)
    record = root / "agent_output/verification/runtime_verifier_records/run/rev-1/turn_0001_retry_0000.json"
    return service, context, result, guard, record


async def publish(values):
    service, context, result, guard, _ = values
    return await service.write(context=context, runtime_result=result, guard_contract=guard, guard_decision={"action": "accept"})


async def test_support_artifacts_share_captured_nested_values(tmp_path, monkeypatch):
    values = publication(tmp_path)
    _, _, result, guard, record = values
    hold = hold_path(monkeypatch, "mkdir", record.parent)
    task = asyncio.create_task(publish(values))
    try:
        await wait_entered(hold)
        result.evidence_summary["nested"]["value"] = "mutated"
        guard["violations"][0]["code"] = "mutated"
        hold.release.set()
        written = await task
        first, latest = await asyncio.gather(asyncio.to_thread(record.read_bytes),
                                            asyncio.to_thread((tmp_path / written.latest_path).read_bytes))
        assert first == latest
        payload = json.loads(first)
        assert payload["evidence_summary"]["nested"]["value"] == "original"
        assert payload["guard_contract"]["violations"][0]["code"] == "original"
        assert payload["artifact_authority"] == "support_only"
        assert payload["authored_output"] is False
    finally:
        await settle(task, hold)


async def test_support_artifact_resolution_keeps_sqlite_responsive(tmp_path, monkeypatch, record_property):
    values = publication(tmp_path)
    hold = hold_path(monkeypatch, "resolve", values[-1], watchdog=0.8)
    started = time.perf_counter()
    task = asyncio.create_task(publish(values))
    try:
        await wait_entered(hold)
        elapsed = await sqlite_response(tmp_path / "response.sqlite3", record_property, started)
        assert elapsed < 0.5
        assert hold.thread != threading.get_ident()
        hold.release.set()
        await task
    finally:
        await settle(task, hold)


async def test_support_artifact_parent_retains_repeated_cancellation(tmp_path, monkeypatch, record_property):
    values = publication(tmp_path)
    hold = hold_path(monkeypatch, "mkdir", values[-1].parent)
    task = asyncio.create_task(publish(values))
    try:
        await cancel_while_held(task, hold, tmp_path / "response.sqlite3", record_property)
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("operation", ["open", "write", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_support_publication_retains_native_stream_and_finishes_history(
    tmp_path, monkeypatch, record_property, operation, stop,
):
    values = publication(tmp_path)
    hold = hold_stream(monkeypatch, values[-1], operation)
    task = asyncio.create_task(publish(values))
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_while_held
        await interrupt(task, hold, tmp_path / "response.sqlite3", record_property)
        assert hold.streams and all(stream.closed for stream in hold.streams)
        index_path = tmp_path / "agent_output/verification/runtime_verification_index.json"
        index = json.loads(await asyncio.to_thread(index_path.read_bytes))
        assert index["history_count"] == 1
        assert index["artifact_authority"] == "support_only"
    finally:
        await settle(task, hold)


async def test_support_publication_native_failure_survives_cancellation(tmp_path, monkeypatch):
    values = publication(tmp_path)
    hold = hold_stream(monkeypatch, values[-1], "write", failure=True)
    task = asyncio.create_task(publish(values))
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        assert not task.done()
        hold.release.set()
        with pytest.raises(OSError, match="controlled native stream failure"):
            await task
        assert all(stream.closed for stream in hold.streams)
        assert await asyncio.to_thread(values[-1].is_file)
        assert not await asyncio.to_thread((tmp_path / "agent_output/verification/runtime_verification.json").exists)
    finally:
        await settle(task, hold)
