"""Integration: actual trust packages settle before interruption can publish authority."""
from __future__ import annotations

import asyncio

import pytest

from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.runtime_verification_hold import wait_entered
from tests.helpers.trust_handoff_ownership import (
    RUN_ID,
    PackageProbe,
    assert_pending_authority,
    prepare_handoff,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("boundary", ["resolve", "manifest", "artifact", "close"])
@pytest.mark.parametrize("rejected", [False, True])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_interrupted_real_package_finishes_before_caller_and_does_not_admit(
        tmp_path, monkeypatch, record_property, boundary, rejected, stop):
    package, _submitted, execution, events = await prepare_handoff(tmp_path, rejected=rejected)
    probe = PackageProbe(monkeypatch, package, boundary)
    task = asyncio.create_task(execution.start_if_ready(RUN_ID))
    try:
        waiter = await interrupt_held_read(task, probe, stop, tmp_path / "responsive.db", record_property)
        await assert_pending_authority(execution, events)
        probe.release.set()
        with pytest.raises(TimeoutError if stop == "timeout" else asyncio.CancelledError):
            await waiter
        probe.assert_closed()
        report, = probe.reports
        assert report["result"] == ("rejected" if rejected else "accepted")
        assert report["rejection_reason"] == ("package_digest_mismatch" if rejected else None)
        await assert_pending_authority(execution, events)
        assert not await asyncio.to_thread((tmp_path / "b.txt").exists)
    finally:
        await probe.cleanup(task)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_real_artifact_read_failure_retains_identity_without_terminal_receipt(
        tmp_path, monkeypatch, record_property, stop):
    package, _submitted, execution, events = await prepare_handoff(tmp_path)
    failure = OSError("controlled failure after actual handoff artifact read")
    probe = PackageProbe(monkeypatch, package, "artifact", failure=failure)
    task = asyncio.create_task(execution.start_if_ready(RUN_ID))
    try:
        if stop == "none":
            await wait_entered(probe)
            waiter = task
        else:
            waiter = await interrupt_held_read(task, probe, stop, tmp_path / "responsive.db", record_property)
        probe.release.set()
        with pytest.raises(OSError) as caught:
            await waiter
        assert caught.value is failure
        probe.assert_closed()
        assert probe.reports == []
        await assert_pending_authority(execution, events)
    finally:
        await probe.cleanup(task)


async def test_manifest_read_failure_keeps_existing_rejection_classification(tmp_path, monkeypatch):
    package, _submitted, execution, events = await prepare_handoff(tmp_path)
    probe = PackageProbe(monkeypatch, package, "manifest", failure=OSError("controlled manifest read refusal"))
    task = asyncio.create_task(execution.start_if_ready(RUN_ID))
    try:
        await wait_entered(probe)
        probe.release.set()
        rejected = await task
        probe.assert_closed()
        assert rejected.status == "completed" and rejected.stop_reason == "package_manifest_schema_invalid"
        report, = probe.reports
        assert report["result"] == "rejected" and report["failure_detail"] == "parse"
        rows = await events.list_for_run(RUN_ID)
        assert [event.event_type for event in rows] == ["run_submitted", "trust_handoff_rejected", "run_completed"]
        assert rows[-1].payload["outcome"] == "handoff_rejected"
    finally:
        await probe.cleanup(task)
