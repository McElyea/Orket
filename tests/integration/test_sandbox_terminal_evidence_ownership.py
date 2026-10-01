"""Integration: actual terminal files/SQLite; no Docker resources or Docker proof."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_sandbox_lifecycle_repository import AsyncSandboxLifecycleRepository
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_runtime_lifecycle_service import SandboxRuntimeLifecycleService
from orket.application.services.sandbox_terminal_evidence_service import SandboxTerminalEvidenceService
from orket.core.domain.sandbox_lifecycle import SandboxState, TerminalReason
from tests.helpers.evidence_ownership import hold_native_call, settle_evidence, timeout_evidence_while_held
from tests.helpers.runtime_verification_hold import (
    cancel_while_held,
    hold_path,
    hold_stream,
    sqlite_response,
    wait_entered,
)
from tests.integration.test_sandbox_terminal_outcome_service import _record, _Runner

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
AT = "2026-03-11T00:10:00+00:00"


def publication(root):
    values = {"sandbox_id": "sb-1", "terminal_reason": TerminalReason.SUCCESS, "created_at": AT,
              "payload": {"nested": {"value": "original"}}}
    document = {**values, "terminal_reason": TerminalReason.SUCCESS.value}
    digest = hashlib.sha256(json.dumps(document, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    path = root / "sb-1" / f"{TerminalReason.SUCCESS.value}-{digest[:16]}.json"
    content = json.dumps(document, indent=2, sort_keys=True).replace("\n", os.linesep).encode("utf-8")
    return values, path, content


@pytest.fixture
def terminal(tmp_path):
    root = tmp_path / "evidence"
    return SandboxTerminalEvidenceService(evidence_root=root), publication(root)


@pytest.mark.parametrize("operation", ["mkdir", "open", "write", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
async def test_terminal_export_retains_native_file_attempt(terminal, tmp_path, monkeypatch, record_property, operation, stop):
    service, (values, path, content) = terminal
    hold = (hold_path(monkeypatch, operation, path.parent) if operation == "mkdir"
            else hold_stream(monkeypatch, path, operation))
    task = asyncio.create_task(service.export(**values))
    try:
        interrupt = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
        await interrupt(task, hold, tmp_path / "responsive.sqlite3", record_property)
        assert hold.thread != threading.get_ident()
        assert await asyncio.to_thread(path.read_bytes) == content
        assert all(stream.closed for stream in getattr(hold, "streams", []))
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("operation", ["write", "close"])
async def test_terminal_native_failure_survives_repeated_cancellation(terminal, monkeypatch, operation):
    service, (values, path, _content) = terminal
    hold = hold_stream(monkeypatch, path, operation, failure=True)
    task = asyncio.create_task(service.export(**values))
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done(), "failed file attempt escaped before settlement"
        hold.release.set()
        with pytest.raises(OSError, match="controlled native stream failure"):
            await task
        assert hold.finished.is_set() and all(stream.closed for stream in hold.streams)
        assert await asyncio.to_thread(path.is_file), "failure must not hide the partial file effect"
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("change_cwd", [False, True])
async def test_terminal_export_captures_nested_values_and_relative_destination(tmp_path, monkeypatch, change_cwd):
    monkeypatch.chdir(tmp_path)
    service = await asyncio.to_thread(SandboxTerminalEvidenceService, evidence_root=Path("evidence"))
    values, relative, content = publication(Path("evidence"))
    other = tmp_path / "other"
    await asyncio.to_thread(other.mkdir)
    hold = hold_native_call(monkeypatch, Path, "mkdir", lambda path, **_kwargs: path.name == "sb-1")
    task = asyncio.create_task(service.export(**values))
    try:
        await wait_entered(hold)
        values["payload"]["nested"]["value"] = "mutated"
        service.evidence_root = other / "replaced-root"
        if change_cwd:
            monkeypatch.chdir(other)
        hold.release.set()
        assert await task == str(relative), "returned reference spelling is preserved"
        assert await asyncio.to_thread((tmp_path / relative).read_bytes) == content
        assert not await asyncio.to_thread((other / relative).exists)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("stop", ["none", "cancel", "timeout"])
async def test_terminal_truth_waits_for_closed_evidence(tmp_path, monkeypatch, record_property, stop):
    repo = AsyncSandboxLifecycleRepository(tmp_path / "lifecycle.sqlite3")
    truth = AsyncControlPlaneRecordRepository(tmp_path / "truth.sqlite3")
    original = _record()
    await repo.save_record(original)
    lifecycle = await asyncio.to_thread(partial(SandboxRuntimeLifecycleService,
        repository=repo, command_runner=_Runner(), instance_id="runner-a", docker_context="desktop-linux",
        docker_host_id="host-a", terminal_evidence_root=tmp_path / "evidence",
        control_plane_publication=ControlPlanePublicationService(repository=truth)))
    values, path, _content = publication(tmp_path / "evidence")
    hold = hold_stream(monkeypatch, path, "close")
    task = asyncio.create_task(lifecycle.terminal_outcomes.record_workflow_terminal_outcome(
        sandbox_id="sb-1", terminal_reason=TerminalReason.SUCCESS, evidence_payload=values["payload"],
        operation_id_prefix="native-evidence", expected_owner_instance_id="runner-a", expected_lease_epoch=1,
        terminal_at=AT))
    try:
        await wait_entered(hold)
        assert await repo.get_record("sb-1") == original
        assert await truth.get_final_truth(run_id="run-1") is None
        assert await sqlite_response(tmp_path / "responsive.sqlite3", record_property) < 0.5
        if stop == "none":
            hold.release.set()
            assert (await task).state is SandboxState.TERMINAL
            assert (await truth.get_final_truth(run_id="run-1")).authoritative_result_ref == str(path)
        else:
            interrupt = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
            await interrupt(task, hold, tmp_path / "responsive.sqlite3", record_property)
            assert await repo.get_record("sb-1") == original
            assert await truth.get_final_truth(run_id="run-1") is None
        assert hold.finished.is_set() and all(stream.closed for stream in hold.streams)
    finally:
        await settle_evidence(task, hold)
