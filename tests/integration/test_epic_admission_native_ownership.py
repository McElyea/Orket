"""Epic admission binds inputs and settles native journal work before return."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

import pytest

from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.application.services.epic_admission_service import EpicAdmissionService
from tests.helpers.card_epic_ownership import hold_sqlite
from tests.helpers.evidence_ownership import hold_native_call, timeout_evidence_while_held
from tests.helpers.runtime_verification_hold import cancel_while_held, hold_path, settle, wait_entered
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def inputs(tmp_path):
    repository = SQLiteEpicPublicationRepository(tmp_path / "runtime.sqlite3")
    service = EpicAdmissionService(repository, owner_id=lambda: "owner", now=lambda: "2026-09-28T00:00:00+00:00")
    request = {"scope": {"workspace": str(tmp_path / "workspace")}, "build_id": "build",
               "epic": {"issues": [{"id": "card"}]}}
    return repository, service, request, {"kind": "fixture", "nested": {"binding": "original"}}


async def interrupt(task, hold, tmp_path, record_property, stop):
    operation = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
    await operation(task, hold, tmp_path / "responsive.sqlite3", record_property)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
# Layer: integration
async def test_epic_claim_resolution_settles_before_cancellation_without_admission(tmp_path, monkeypatch, record_property, stop):
    repository, service, request, binding = inputs(tmp_path)
    async with repository.transaction("run"):
        pass
    before = await logical_state(repository.db_path)
    hold = hold_path(monkeypatch, "resolve", Path(request["scope"]["workspace"]))
    task = asyncio.create_task(service.claim("run", request, binding))
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert await logical_state(repository.db_path) == before
        async with repository.transaction("run") as transaction:
            assert await transaction.get_admission() is None
    finally:
        await settle(task, hold)


# Layer: integration
async def test_epic_claim_keeps_captured_request_and_export_binding(tmp_path, monkeypatch):
    repository, service, request, binding = inputs(tmp_path)
    expected_request, expected_binding = deepcopy(request), deepcopy(binding)
    hold = hold_path(monkeypatch, "resolve", Path(request["scope"]["workspace"]))
    task = asyncio.create_task(service.claim("run", request, binding))
    try:
        await wait_entered(hold)
        request["build_id"] = "substituted-build"
        request["epic"]["issues"][0]["id"] = "substituted-card"
        binding["nested"]["binding"] = "substituted-binding"
        hold.release.set()
        admission = await task
        assert admission.request == expected_request and admission.export_binding == expected_binding
        assert "build:build" in admission.resources and "card:card" in admission.resources
        assert not any("substituted" in resource for resource in admission.resources)
        async with repository.transaction("run") as transaction:
            assert await transaction.get_admission() == admission
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
# Layer: integration
async def test_epic_journal_parent_settles_before_return_without_entering_transaction(tmp_path, monkeypatch, record_property, stop):
    repository = SQLiteEpicPublicationRepository(tmp_path / "new" / "runtime.sqlite3")
    entered = []
    hold = hold_path(monkeypatch, "mkdir", repository.db_path.parent)

    async def open_transaction():
        async with repository.transaction("run"):
            entered.append(True)

    task = asyncio.create_task(open_transaction())
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert entered == [] and hold.finished.is_set() and not hold.expired
        assert not await asyncio.to_thread(repository.db_path.exists)
        assert await asyncio.to_thread(repository.db_path.parent.is_dir)
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("phase", ["commit", "close"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
# Layer: integration
async def test_epic_journal_commit_and_close_are_retained(tmp_path, monkeypatch, record_property, phase, stop):
    repository, service, request, binding = inputs(tmp_path)
    admission = await service.claim("seed", request, binding)
    hold = hold_sqlite(monkeypatch, repository.db_path, phase)

    async def write_marker():
        async with repository.transaction("seed") as transaction:
            current = await transaction.get_admission()
            assert current == admission
            await transaction.save_admission(current.model_copy(update={"initialization_started": True}))

    task = asyncio.create_task(write_marker())
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert set(hold.closed) == {id(connection) for connection in hold.connections}
        async with repository.transaction("seed") as transaction:
            retained = await transaction.get_admission()
            assert retained.initialization_started and retained.owner_id == admission.owner_id
            assert retained.phase == "active" and retained.recoveries == ()
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["none", "cancel"])
# Layer: integration
async def test_epic_journal_rolls_back_before_reporting_body_failure(tmp_path, monkeypatch, stop):
    repository, service, request, binding = inputs(tmp_path)
    admission = await service.claim("seed", request, binding)
    before = await logical_state(repository.db_path)
    hold = hold_sqlite(monkeypatch, repository.db_path, "rollback")
    failure = RuntimeError("controlled transaction body failure")

    async def rejected_body():
        async with repository.transaction("seed") as transaction:
            await transaction.save_admission(admission.model_copy(update={"initialization_started": True}))
            raise failure

    task = asyncio.create_task(rejected_body())
    try:
        await wait_entered(hold)
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and not hold.finished.is_set()
        hold.release.set()
        with pytest.raises(RuntimeError) as observed:
            await task
        assert observed.value is failure
        assert set(hold.closed) == {id(connection) for connection in hold.connections}
        assert await logical_state(repository.db_path) == before
    finally:
        await settle(task, hold)


# Layer: integration
async def test_epic_parent_failure_retains_partial_directory_and_no_database(tmp_path, monkeypatch):
    repository = SQLiteEpicPublicationRepository(tmp_path / "new" / "runtime.sqlite3")
    original, failure = Path.mkdir, OSError("controlled directory result failure")

    def mkdir(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == repository.db_path.parent:
            raise failure
        return result

    monkeypatch.setattr(Path, "mkdir", mkdir)
    hold = hold_native_call(monkeypatch, Path, "mkdir", selected=lambda path, *_args, **_kwargs: path == repository.db_path.parent)

    async def open_transaction():
        async with repository.transaction("run"):
            raise AssertionError("failed preflight must not enter caller body")

    task = asyncio.create_task(open_transaction())
    try:
        await wait_entered(hold)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and not hold.finished.is_set()
        hold.release.set()
        with pytest.raises(OSError) as observed:
            await task
        assert observed.value is failure
        assert not await asyncio.to_thread(repository.db_path.exists)
        assert await asyncio.to_thread(repository.db_path.parent.is_dir)
    finally:
        await settle(task, hold)
