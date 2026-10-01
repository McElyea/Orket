"""Integration: real failure artifacts and saved logs retain invocation-selected inputs."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import aiofiles.threadpool
import pytest
from pydantic import ValidationError

import orket.application.services.failure_report_service as reports
from orket.core.domain.failure_reporter import PolicyViolationReport
from tests.helpers.evidence_ownership import hold_native_call, settle_evidence
from tests.helpers.governed_read_ownership import interrupt_held_read
from tests.helpers.runtime_verification_hold import hold_stream, wait_entered

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def report_value():
    return PolicyViolationReport(timestamp="2026-09-28T12:00:00+00:00", session_id="selected-session",
        card_id="selected-card", violation_type="tool_gate", detail="selected failure",
        attempted_action={"arguments": {"path": "original"}}, remedy_suggestion="inspect the retained report",
        active_roles=("developer",))


def target(root):
    return root / "agent_output/policy_violation_selected-card.json"


def read_publication(root):
    content = json.loads(target(root).read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (root / "orket.log").read_text(encoding="utf-8").splitlines()]
    saved = [record for record in records if record["event"] == "policy_violation_report_saved"]
    assert len(saved) == 1
    payload = saved[0]["data"]
    assert (payload["session_id"], payload["card_id"], payload["path"]) == (
        content["session_id"], content["card_id"], str(target(root)))
    return content


def observe_report_streams(monkeypatch, root):
    original, streams = aiofiles.threadpool.sync_open, []

    def opened(path, *args, **kwargs):
        stream = original(path, *args, **kwargs)
        if Path(path) == target(root):
            streams.append(stream)
        return stream

    monkeypatch.setattr(aiofiles.threadpool, "sync_open", opened)
    return streams


def hold_phase(monkeypatch, root, phase):
    if phase.startswith("report_") or phase.startswith("log_"):
        family, operation = phase.split("_", 1)
        hold = hold_stream(monkeypatch, target(root) if family == "report" else root / "orket.log", operation)
        hold.expired = False
        return hold
    path = {"root": root, "directory": root / "agent_output", "path": target(root),
            "mkdir": root / "agent_output"}[phase]
    operation = "mkdir" if phase == "mkdir" else "resolve"
    return hold_native_call(monkeypatch, Path, operation, lambda selected, *_a, **_k: selected == path)


async def test_workspace_rebinding_after_first_yield_cannot_redirect_publication(tmp_path):
    root, changed = tmp_path / "selected", tmp_path / "changed"
    service, report = reports.FailureReportService(root), report_value()
    expected, mutations = report.model_dump(mode="json"), []

    def mutate():
        mutations.append(True)
        service.workspace = changed
        report.attempted_action["arguments"]["path"] = "changed"

    # Standard call_soon FIFO places the mutation after publish's synchronous
    # admission but before its newly admitted child first executes. No fake I/O.
    asyncio.get_running_loop().call_soon(mutate)
    path = await service.publish(report)
    assert mutations == [True] and path == target(root)
    assert await asyncio.to_thread(read_publication, root) == expected
    assert not await asyncio.to_thread(changed.exists)


async def test_relative_workspace_binds_before_held_native_resolution(tmp_path, monkeypatch):
    first, changed = tmp_path / "first", tmp_path / "changed"
    await asyncio.to_thread(first.mkdir)
    await asyncio.to_thread(changed.mkdir)
    root = first / "workspace"
    monkeypatch.chdir(first)
    service, report = reports.FailureReportService(Path("workspace")), report_value()
    hold = hold_native_call(monkeypatch, Path, "resolve",
        lambda path, *_a, **_k: path in {Path("workspace"), root})
    task = asyncio.create_task(service.publish(report))
    try:
        await wait_entered(hold)
        monkeypatch.chdir(changed)
        hold.release.set()
        assert await task == target(root)
        assert await asyncio.to_thread(read_publication, root) == report.model_dump(mode="json")
        assert not await asyncio.to_thread((changed / "workspace").exists)
    finally:
        monkeypatch.chdir(first)
        await settle_evidence(task, hold)


async def test_supported_frozen_identity_and_nested_rendered_content_remain_consistent(tmp_path, monkeypatch):
    report = report_value()
    expected = report.model_dump(mode="json")
    hold = hold_phase(monkeypatch, tmp_path, "root")
    task = asyncio.create_task(reports.FailureReportService(tmp_path).publish(report))
    try:
        await wait_entered(hold)
        with pytest.raises(ValidationError, match="frozen_instance"):
            report.card_id = "changed"
        with pytest.raises(ValidationError, match="frozen_instance"):
            report.session_id = "changed"
        report.attempted_action["arguments"]["path"] = "changed"
        hold.release.set()
        assert await task == target(tmp_path)
        assert await asyncio.to_thread(read_publication, tmp_path) == expected
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("phase", ["root", "directory", "mkdir", "path", "report_open", "report_write",
    "report_close", "log_open", "log_write", "log_close"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_complete_publication_retains_real_native_file_and_saved_log(
    tmp_path, monkeypatch, record_property, phase, mode,
):
    report = report_value()
    hold = hold_phase(monkeypatch, tmp_path, phase)
    streams = observe_report_streams(monkeypatch, tmp_path)
    task, waiter = asyncio.create_task(reports.FailureReportService(tmp_path).publish(report)), None
    try:
        waiter = await interrupt_held_read(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        if phase.startswith("log_"):
            assert streams and all(stream.closed for stream in streams), "saved log preceded report closure"
            assert json.loads(await asyncio.to_thread(target(tmp_path).read_text)) == report.model_dump(mode="json")
        else:
            assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
        hold.release.set()
        with pytest.raises(TimeoutError if mode == "timeout" else asyncio.CancelledError):
            await waiter
        assert hold.finished.is_set() and not hold.expired
        assert streams and all(stream.closed for stream in streams)
        assert all(stream.closed for stream in getattr(hold, "streams", ()))
        assert await asyncio.to_thread(read_publication, tmp_path) == report.model_dump(mode="json")
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("phase", ["root", "saved_event"])
@pytest.mark.parametrize("mode", ["cancel", "timeout"])
async def test_native_failure_remains_exact_with_truthful_partial_publication(
    tmp_path, monkeypatch, record_property, phase, mode,
):
    report, failure = report_value(), OSError("native failure publication acknowledgement failed")
    owner, name = (Path, "resolve") if phase == "root" else (reports, "log_event")
    original = getattr(owner, name)

    def failed(*args, **kwargs):
        result = original(*args, **kwargs)
        if phase == "saved_event" or args[0] == tmp_path:
            raise failure
        return result

    monkeypatch.setattr(owner, name, failed)
    hold = hold_native_call(monkeypatch, owner, name,
        lambda *args, **_k: phase == "saved_event" or args[0] == tmp_path)
    task, waiter = asyncio.create_task(reports.FailureReportService(tmp_path).publish(report)), None
    try:
        waiter = await interrupt_held_read(task, hold, mode, tmp_path / "sibling.sqlite3", record_property)
        hold.release.set()
        with pytest.raises(OSError) as observed:
            await waiter
        assert observed.value is failure and hold.finished.is_set() and not hold.expired
        if phase == "saved_event":
            assert await asyncio.to_thread(read_publication, tmp_path) == report.model_dump(mode="json")
        else:
            assert not await asyncio.to_thread(target(tmp_path).exists)
            assert not await asyncio.to_thread((tmp_path / "orket.log").exists)
    finally:
        await settle_evidence(task, hold)


@pytest.mark.parametrize("card_id", ["", "../escape", "bad/name", "bad:stream", "bad\\name"])
async def test_invalid_identity_refuses_before_artifact_or_saved_event(tmp_path, card_id):
    report = report_value().model_copy(update={"card_id": card_id})
    with pytest.raises(ValueError, match="portable file-name"):
        await reports.FailureReportService(tmp_path).publish(report)
    assert not await asyncio.to_thread((tmp_path / "agent_output").exists)
    assert not await asyncio.to_thread((tmp_path / "orket.log").exists)


async def test_real_file_collision_preserves_operator_directory_and_has_no_saved_event(tmp_path):
    await asyncio.to_thread(target(tmp_path).mkdir, parents=True)
    with pytest.raises(OSError):
        await reports.FailureReportService(tmp_path).publish(report_value())
    assert await asyncio.to_thread(target(tmp_path).is_dir)
    assert not await asyncio.to_thread((tmp_path / "orket.log").exists)


async def test_drive_relative_workspace_refuses_before_publication(tmp_path, monkeypatch):
    if not tmp_path.drive:
        pytest.skip("Windows drive-relative path policy")
    monkeypatch.chdir(tmp_path)
    service = reports.FailureReportService(Path(tmp_path.drive + "workspace"))
    with pytest.raises(ValueError, match="E_FILE_TOOL_DRIVE_RELATIVE_ROOT_UNSUPPORTED"):
        await service.publish(report_value())
    assert not await asyncio.to_thread((tmp_path / "workspace").exists)
