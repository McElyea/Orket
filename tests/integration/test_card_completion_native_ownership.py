"""Card metadata/receipt attempts retain native work before authority can escape."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from orket.adapters.storage import card_acceptance_artifacts
from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain.records import IssueRecord
from orket.schema import CardStatus
from tests.helpers.card_completion import completion_components, text_acceptance
from tests.helpers.card_epic_ownership import hold_sqlite
from tests.helpers.evidence_ownership import hold_native_call, timeout_evidence_while_held
from tests.helpers.runtime_verification_hold import cancel_while_held, hold_path, settle, wait_entered
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def card_fixture(tmp_path, stage):
    workspace = tmp_path / "workspace"
    repo, service = completion_components(tmp_path / "cards.sqlite3", workspace)
    definition = text_acceptance("agent_output/accepted.txt", "accepted", workload_id="native-card")
    await AsyncFileTools(workspace).write_file("agent_output/accepted.txt", "accepted")
    await repo.save(IssueRecord(id="card", summary="Literal acceptance", seat="developer", status=CardStatus.CODE_REVIEW,
        params={"completion_acceptance": definition.model_dump(mode="json")}))
    context = evaluation = None
    if stage != "new":
        context = await service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt")
        evaluation = await service.evaluate_attempt(repo, context)
        assert evaluation.decision.sufficient
    if stage == "completed":
        await repo.update_status("card", CardStatus.DONE, completion_request=evaluation.request)
    return repo, service, context, evaluation


async def interrupt(task, hold, tmp_path, record_property, stop):
    operation = cancel_while_held if stop == "cancel" else timeout_evidence_while_held
    await operation(task, hold, tmp_path / "responsive.sqlite3", record_property)


@pytest.mark.parametrize("route", ["begin", "evaluate", "receipt"])
@pytest.mark.parametrize("stop", ["cancel", "timeout"])
# Layer: integration
async def test_card_metadata_interruption_waits_for_native_resolution(tmp_path, monkeypatch, record_property, route, stop):
    stage = {"begin": "new", "evaluate": "evaluated", "receipt": "completed"}[route]
    repo, service, context, _ = await card_fixture(tmp_path, stage)
    before = await logical_state(repo.db_path)
    selected = Path(repo.db_path) if route == "receipt" else service.workspace_root
    hold = hold_path(monkeypatch, "resolve", selected)
    calls = {"begin": lambda: service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt"),
             "evaluate": lambda: service.evaluate_attempt(repo, context), "receipt": lambda: repo.read_completion_receipt("card")}
    task = asyncio.create_task(calls[route]())
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert hold.finished.is_set() and not hold.expired
        assert await logical_state(repo.db_path) == before
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
@pytest.mark.parametrize("capture_fails", [False, True], ids=["captured", "diagnostic"])
# Layer: integration
async def test_final_authorization_retains_artifact_capture_before_writer_release(tmp_path, monkeypatch, record_property, stop, capture_fails):
    repo, service, _, evaluation = await card_fixture(tmp_path, "evaluated")
    before = await logical_state(repo.db_path)
    original = card_acceptance_artifacts._capture

    def capture(*args):
        result = original(*args)
        if capture_fails:
            raise OSError("controlled post-capture failure during cancellation")
        return result

    monkeypatch.setattr(card_acceptance_artifacts, "_capture", capture)
    hold = hold_native_call(monkeypatch, card_acceptance_artifacts, "_capture")
    task = asyncio.create_task(repo.update_status("card", CardStatus.DONE, completion_request=evaluation.request))
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert hold.finished.is_set() and not hold.expired
        assert await logical_state(repo.db_path) == before
        assert (await repo.get_by_id("card")).status is CardStatus.CODE_REVIEW
        assert await repo.read_completion_receipt("card") is None
        assert await repo.get_card_history("card") == []
        monkeypatch.setattr(card_acceptance_artifacts, "_capture", original)
        receipt = await repo.update_status("card", CardStatus.DONE, completion_request=evaluation.request)
        assert await repo.read_completion_receipt("card") == receipt
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["cancel", "timeout"])
# Layer: integration
async def test_receipt_read_retains_native_sqlite_close(tmp_path, monkeypatch, record_property, stop):
    repo, _, _, _ = await card_fixture(tmp_path, "completed")
    receipt = await repo.read_completion_receipt("card")
    before = await logical_state(repo.db_path)
    hold = hold_sqlite(monkeypatch, Path(repo.db_path), "close")
    task = asyncio.create_task(repo.read_completion_receipt("card"))
    try:
        await interrupt(task, hold, tmp_path, record_property, stop)
        assert set(hold.closed) == {id(connection) for connection in hold.connections}
        assert await logical_state(repo.db_path) == before
        assert await repo.read_completion_receipt("card") == receipt
    finally:
        await settle(task, hold)


# Layer: integration
async def test_card_admission_binds_relative_workspace_before_native_resolution(tmp_path, monkeypatch):
    repo, service, _, _ = await card_fixture(tmp_path, "new")
    monkeypatch.chdir(tmp_path)
    service.workspace_root = Path("workspace")
    hold = hold_native_call(monkeypatch, Path, "resolve", selected=lambda path, *_args, **_kwargs: path.name == "workspace")
    task = asyncio.create_task(service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt"))
    try:
        await wait_entered(hold)
        service.workspace_root = tmp_path / "other"
        monkeypatch.chdir(tmp_path.parent)
        hold.release.set()
        context = await task
        assert context.workspace_root == str(tmp_path / "workspace")
        assert (await repo.get_by_id("card")).completion_context == context
        assert await repo.read_completion_receipt("card") is None
    finally:
        await settle(task, hold)


@pytest.mark.parametrize("stop", ["none", "cancel"])
# Layer: integration
async def test_card_native_resolution_failure_keeps_identity_and_retained_state(tmp_path, monkeypatch, stop):
    repo, service, _, _ = await card_fixture(tmp_path, "new")
    before = await logical_state(repo.db_path)
    original, failure = Path.resolve, OSError("controlled root observation failure")

    def resolve(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == service.workspace_root:
            raise failure
        return result

    monkeypatch.setattr(Path, "resolve", resolve)
    hold = hold_native_call(monkeypatch, Path, "resolve", selected=lambda path, *_args, **_kwargs: path == service.workspace_root)
    task = asyncio.create_task(service.begin_attempt(repo, card_id="card", run_id="run", attempt_id="attempt"))
    try:
        await wait_entered(hold)
        if stop == "cancel":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.02)
        assert not task.done() and not hold.finished.is_set()
        hold.release.set()
        with pytest.raises(OSError) as observed:
            await task
        assert observed.value is failure
        assert await logical_state(repo.db_path) == before
        assert (await repo.get_by_id("card")).completion_context is None
    finally:
        await settle(task, hold)


# Layer: integration
async def test_final_authorization_preserves_capture_diagnostics_without_authority(tmp_path, monkeypatch):
    repo, _, _, evaluation = await card_fixture(tmp_path, "evaluated")
    before = await logical_state(repo.db_path)
    original = card_acceptance_artifacts._capture

    def capture(*args):
        original(*args)
        raise OSError("controlled post-capture failure")

    with monkeypatch.context() as patch:
        patch.setattr(card_acceptance_artifacts, "_capture", capture)
        with pytest.raises(CardCompletionRejected, match="E_CARD_COMPLETION_ACCEPTANCE_REQUIRED") as observed:
            await repo.update_status("card", CardStatus.DONE, completion_request=evaluation.request)
    assert not observed.value.decision.sufficient
    assert await logical_state(repo.db_path) == before
    assert await repo.read_completion_receipt("card") is None
    receipt = await repo.update_status("card", CardStatus.DONE, completion_request=evaluation.request)
    assert await repo.read_completion_receipt("card") == receipt
