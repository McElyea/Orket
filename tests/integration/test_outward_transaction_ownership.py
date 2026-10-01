"""Integration: real outward admission and lexical transaction cleanup retain native work."""
from __future__ import annotations

import asyncio

import pytest

from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.outward_store_ownership import (
    NativeStoreProbe,
    initialize,
    run_record,
    state,
    stores_and_service,
    submission,
)
from tests.helpers.runtime_verification_hold import wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("phase", ["resolve", "connect", "wal", "begin", "schema", "body", "commit", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_public_submission_retains_resource_phase_through_interruption(
    tmp_path, monkeypatch, record_property, phase, mode,
):
    path = tmp_path / "selected.sqlite3"
    stores, _unit, service = stores_and_service(path)
    await initialize(stores)
    probe = NativeStoreProbe(monkeypatch, path, phase)
    task, waiter = asyncio.create_task(service.submit(submission())), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        await probe.assert_settled()
        counts = await state(path)
        expected = int(phase in {"commit", "close"})
        assert counts["outward_runs"] == counts["run_events"] == expected
        if expected:
            # Real application validation proves retained control-plane authority too.
            assert (await service.submit(submission())).run_id == "owned-run"
            assert (await state(path))["run_events"] == 1
        elif phase == "resolve":
            assert probe.connections == []
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("phase,body_fails", [("rollback", True), ("close", True), ("close", False)])
@pytest.mark.parametrize("mode", ["none", "cancel", "timeout"])
async def test_native_cleanup_cancellation_keeps_its_identity_and_actual_effects(
    tmp_path, monkeypatch, record_property, phase, body_fails, mode,
):
    path = tmp_path / "selected.sqlite3"
    stores, unit, service = stores_and_service(path)
    await initialize(stores)
    body_failure = ValueError("application body failed before native cleanup cancellation")
    native_failure = asyncio.CancelledError("native cleanup acknowledgement cancelled")
    probe = NativeStoreProbe(monkeypatch, path, phase, failure=native_failure)

    async def fail_body():
        async with unit.transaction() as transaction:
            await transaction.create_run(run_record())
            raise body_failure

    task = asyncio.create_task(fail_body() if body_fails else service.submit(submission()))
    waiter = task
    try:
        if mode == "none":
            await wait_entered(probe)
        else:
            waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError) as observed:
            await waiter
        retained = observed.value.__cause__ if mode == "timeout" else observed.value
        assert retained is native_failure
        if body_fails:
            assert retained.__context__ is body_failure
        await probe.assert_settled()
        counts = await state(path)
        assert counts["outward_runs"] == int(not body_fails)
        assert counts["run_events"] == int(not body_fails)
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("phase", ["commit", "close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_committed_admission_is_not_success_when_native_acknowledgement_fails(
    tmp_path, monkeypatch, record_property, phase, mode,
):
    path = tmp_path / "selected.sqlite3"
    stores, _unit, service = stores_and_service(path)
    await initialize(stores)
    failure = OSError("committed admission acknowledgement failed")
    probe = NativeStoreProbe(monkeypatch, path, phase, failure=failure)
    task, waiter = asyncio.create_task(service.submit(submission())), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure
        await probe.assert_settled()
        counts = await state(path)
        assert counts["outward_runs"] == counts["run_events"] == 1
        assert (await service.submit(submission())).run_id == "owned-run"
        assert (await state(path))["run_events"] == 1
    finally:
        await probe.cleanup(task, waiter)


@pytest.mark.parametrize("phase", ["rollback", "close"])
@pytest.mark.parametrize("native_fails", [False, True])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_body_failure_retains_rollback_close_and_native_failure_precedence(
    tmp_path, monkeypatch, record_property, phase, native_fails, mode,
):
    path = tmp_path / "selected.sqlite3"
    stores, unit, _service = stores_and_service(path)
    await initialize(stores)
    body_failure, cleanup_failure = ValueError("application body failed"), OSError("cleanup acknowledgement failed")
    probe = NativeStoreProbe(monkeypatch, path, phase, failure=cleanup_failure if native_fails else None)
    caller = []

    async def body():
        caller.append(asyncio.current_task())
        async with unit.transaction() as transaction:
            assert asyncio.current_task() is caller[0]
            await transaction.create_run(run_record())
            raise body_failure

    task, waiter = asyncio.create_task(body()), None
    try:
        waiter = await interrupt_held_read(task, probe, mode, tmp_path / "sibling.sqlite3", record_property)
        probe.release.set()
        with pytest.raises(OSError if native_fails else ValueError) as observed:
            await waiter
        assert observed.value is (cleanup_failure if native_fails else body_failure)
        if native_fails:
            assert observed.value.__context__ is body_failure
        await probe.assert_settled()
        assert (await state(path))["outward_runs"] == 0
    finally:
        await probe.cleanup(task, waiter)
