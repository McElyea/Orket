"""Bound filesystem operations through real approval, handle and cancellation paths."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import replace
from threading import Event

import pytest

import orket.adapters.storage.bound_filesystem as filesystem
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from orket.core.domain.outward_authorization import args_hash
from tests.helpers.outward_authorization import approve, effect_snapshot, outward_api, submit_sequence
from tests.helpers.outward_authorization import boundary as boundary


def _hold_operation(monkeypatch):
    entered, release, finished = Event(), Event(), Event()
    original = filesystem._operate

    def held(*args):
        entered.set()
        try:
            assert release.wait(timeout=15), "Parent did not release the opened filesystem operation"
            return original(*args)
        finally:
            finished.set()

    monkeypatch.setattr(filesystem, "_operate", held)
    return entered, release, finished


@pytest.mark.integration
# Layer: integration
async def test_approved_filesystem_sequence_retains_arguments_and_results(tmp_path, boundary):
    """Actual mkdir/write/read/delete use the bound path and retain each call's original argument digest."""
    db_path, inputs, calls = boundary
    calls[:] = [
        {"tool": "create_directory", "args": {"path": "."}},
        {"tool": "create_directory", "args": {"path": "nested/inner"}},
        {"tool": "write_file", "args": {"path": "nested/inner/file.txt", "content": {"message": "hello"}}},
        {"tool": "read_file", "args": {"path": "nested/inner/file.txt"}},
        {"tool": "delete_file", "args": {"path": "nested/inner/file.txt"}},
    ]
    async with outward_api(tmp_path, inputs) as (client, context):
        proposal_id = await submit_sequence(client, calls)
        for call in calls:
            response = await approve(client, proposal_id)
            assert response.status_code == 200, response.text
            effect, _journal = await effect_snapshot(db_path, proposal_id)
            assert effect.state == "published"
            assert effect.receipt["event"]["args_hash"] == args_hash(call["args"])
            assert effect.receipt["result"]["ok"] is True, effect.receipt
            if call["tool"] == "read_file":
                assert effect.receipt["result"]["content"] == json.dumps(calls[2]["args"]["content"], indent=2)
            run = await context.outward_run_store.get("bt0-run")
            if run.pending_proposals:
                proposal_id = run.pending_proposals[0]["proposal_id"]
        assert run.status == "completed"
        events = await context.outward_run_event_store.list_for_run("bt0-run")
        assert sum(event.event_type == "tool_invoked" for event in events) == len(calls)
    assert await asyncio.to_thread((tmp_path / "nested/inner").is_dir)
    assert not await asyncio.to_thread((tmp_path / "nested/inner/file.txt").exists)


@pytest.mark.integration
@pytest.mark.parametrize("component", ["parent", "file"])
# Layer: integration
async def test_opened_bound_target_cannot_be_redirected(tmp_path, boundary, monkeypatch, component):
    """Replacement is excluded by Windows handles or remains isolated from POSIX descriptor I/O."""
    _db_path, inputs, calls = boundary
    parent = tmp_path / "original"
    await asyncio.to_thread(parent.mkdir)
    calls[0]["args"]["path"] = "original/output.txt"
    other_parent = tmp_path / "other"
    await asyncio.to_thread(other_parent.mkdir)
    other = other_parent / "output.txt"
    await asyncio.to_thread(other.write_text, "untouched", encoding="utf-8")
    entered, release, finished = _hold_operation(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1])
        task = asyncio.create_task(approve(client, proposal_id))
        moved = tmp_path / "moved"
        before = parent if component == "parent" else parent / "output.txt"
        try:
            assert await asyncio.to_thread(entered.wait, 5), "Operation did not reach opened-handle boundary"
            if os.name == "nt":
                with pytest.raises(PermissionError):
                    await asyncio.to_thread(before.rename, moved)
                actual = parent / "output.txt"
            else:
                await asyncio.to_thread(before.rename, moved)
                await asyncio.to_thread(before.symlink_to, other_parent if component == "parent" else other,
                                        target_is_directory=component == "parent")
                actual = moved / "output.txt" if component == "parent" else moved
            release.set()
            response = await asyncio.wait_for(task, timeout=10)
            assert response.status_code == 200, response.text
            assert finished.is_set()
            assert await asyncio.to_thread(actual.read_text) == calls[0]["args"]["content"]
            assert await asyncio.to_thread(other.read_text) == "untouched"
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=10)
            if await asyncio.to_thread(before.is_symlink):
                await asyncio.to_thread(before.unlink)
        if os.name == "nt":
            await asyncio.to_thread(before.rename, moved)  # Handles were released when the response completed.


@pytest.mark.integration
@pytest.mark.parametrize("cancel_requests", [1, 3])
# Layer: integration
async def test_cancel_waits_for_owned_file_operation_and_retains_uncertain_intent(
    tmp_path, boundary, monkeypatch, cancel_requests,
):
    """Cancellation cannot return while the file thread can still write; a completed uncertain write is not retried."""
    db_path, inputs, calls = boundary
    entered, release, finished = _hold_operation(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, _context):
        proposal_id = await submit_sequence(client, calls[:1])
        task = asyncio.create_task(approve(client, proposal_id))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            for _request in range(cancel_requests):
                task.cancel()
                done, _pending = await asyncio.wait([task], timeout=0.1)
                assert not done and not finished.is_set()
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=10)
            assert finished.is_set()
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=10)
    effect, journal = await effect_snapshot(db_path, proposal_id)
    assert effect.state == "dispatching" and len(journal) == 2
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
    async with outward_api(tmp_path, inputs) as (client, _context):
        assert (await approve(client, proposal_id)).status_code == 409
    await asyncio.to_thread((tmp_path / "first.txt").rename, tmp_path / "closed.txt")


@pytest.mark.integration
# Layer: integration. An expired deadline still waits for actual handle release before publishing timeout evidence.
async def test_bound_filesystem_timeout_waits_for_worker_and_cannot_redispatch(tmp_path, boundary, monkeypatch):
    db_path, inputs, calls = boundary
    entered, release, finished = _hold_operation(monkeypatch)
    async with outward_api(tmp_path, inputs) as (client, context):
        connectors = context.outward_run_execution_service.connector_service
        connectors.connector_registry = BuiltInConnectorRegistry([
            replace(connectors.connector_registry.get("write_file"), timeout_seconds=0.05),
        ])
        proposal_id = await submit_sequence(client, calls[:1])
        task = asyncio.create_task(approve(client, proposal_id))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            done, _pending = await asyncio.wait([task], timeout=0.15)
            assert not done and not finished.is_set()
            release.set()
            response = await asyncio.wait_for(task, timeout=10)
            assert response.status_code == 200 and finished.is_set(), response.text
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=10)
        effect, journal = await effect_snapshot(db_path, proposal_id)
        assert effect.state == "published" and len(journal) == 4
        assert effect.receipt["event"]["outcome"] == "timeout" and effect.receipt["result"]["error"] == "timeout"
        target = tmp_path / "first.txt"
        assert await asyncio.to_thread(target.read_text) == calls[0]["args"]["content"]
        await asyncio.to_thread(target.write_text, "preserve after timeout")
        assert (await approve(client, proposal_id)).status_code == 200
        assert await asyncio.to_thread(target.read_text) == "preserve after timeout"
