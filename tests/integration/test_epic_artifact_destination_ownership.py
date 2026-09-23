"""Layer: integration. Epic approval recovery keeps its captured artifact destination."""
from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services import epic_approval_pause_service as pause_service_module
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.core.contracts.epic_approval_recovery import EpicApprovalRecoveryRequest
from tests.helpers.kernel_state_probe import responsive_sqlite
from tests.integration.test_epic_approval_continuation import approval_engine
from tests.integration.test_epic_approval_recovery import claimed_process, recovery_request

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _stop_child(child) -> None:
    if child.returncode is None:
        child.kill()
    await asyncio.wait_for(child.communicate(), 15)


def _approval_service(engine):
    service = engine._pipeline._build_epic_run_orchestrator().approval_pauses
    assert service is not None
    return service


async def _continue(service, pause, request):
    recovery = EpicApprovalRecoveryRequest.model_validate(request)
    async with service.continuation(
        pause.session_id, pause.request, pause.export_binding, recovery,
    ) as claimed:
        return claimed


def _hold_capture_boundaries(monkeypatch, service):
    state = SimpleNamespace(
        repository_entered=asyncio.Event(), repository_release=asyncio.Event(),
        lock_entered=asyncio.Event(), lock_release=asyncio.Event(),
        transactions=0, locks=0, destinations=[],
    )
    transaction, hold = service.repository.transaction, service.locks.hold
    capture = pause_service_module.capture_approval_destinations

    @asynccontextmanager
    async def held_transaction(session_id):
        async with transaction(session_id) as tx:
            state.transactions += 1
            if state.transactions == 1:
                state.repository_entered.set()
                await asyncio.wait_for(state.repository_release.wait(), 5)
            yield tx

    @asynccontextmanager
    async def held_lock(session_id, *, expected=None):
        async with hold(session_id, expected=expected) as reference:
            state.locks += 1
            state.lock_entered.set()
            await asyncio.wait_for(state.lock_release.wait(), 5)
            yield reference

    def observed_destinations(*args, **kwargs):
        destinations = capture(*args, **kwargs)
        state.destinations.extend(destinations.values())
        return destinations

    monkeypatch.setattr(service.repository, "transaction", held_transaction)
    monkeypatch.setattr(service.locks, "hold", held_lock)
    monkeypatch.setattr(pause_service_module, "capture_approval_destinations", observed_destinations)
    return state


async def _settle(task, state, primary_error: BaseException | None) -> None:
    state.repository_release.set()
    state.lock_release.set()
    if not task.done():
        task.cancel()
    try:
        await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), 10)
    except BaseException as error:
        if primary_error is None:
            raise
        primary_error.add_note(f"Epic destination cleanup also failed: {error!r}")


async def _recovery_rows(service, session_id: str):
    async with service.repository.transaction(session_id) as tx:
        return await tx.approval_pauses.recoveries()


async def test_epic_recovery_keeps_writer_and_workspace_across_repository_and_lock_waits(
    tmp_path, monkeypatch, record_property,
) -> None:
    """Layer: integration. Real recovery reads only the captured A destination."""
    async with claimed_process(tmp_path) as (child, pause):
        await _stop_child(child)
        async with approval_engine(tmp_path, monkeypatch) as engine:
            service = _approval_service(engine)
            writer_a, root_a = service.artifact_writer, tmp_path / "workspace"
            assert Path(writer_a.workspace) == root_a
            root_b, root_c = tmp_path / "workspace-b", tmp_path / "workspace-c"
            state = _hold_capture_boundaries(monkeypatch, service)
            task = asyncio.create_task(_continue(service, pause, recovery_request(pause)))
            primary_error = None
            try:
                await asyncio.wait_for(state.repository_entered.wait(), 5)
                writer_a.workspace = root_b
                service.artifact_writer = TurnArtifactWriter(root_b)
                await responsive_sqlite(tmp_path / "repository-responsive.sqlite3", record_property)
                state.repository_release.set()
                await asyncio.wait_for(state.lock_entered.wait(), 5)
                assert state.destinations and all(
                    row.writer is writer_a and row.workspace == root_a for row in state.destinations)
                writer_a.workspace = root_c
                service.artifact_writer = TurnArtifactWriter(root_c)
                await responsive_sqlite(tmp_path / "lock-responsive.sqlite3", record_property)
                state.lock_release.set()
                claimed = await asyncio.wait_for(asyncio.shield(task), 10)
                assert claimed == pause and state.transactions >= 2 and state.locks == 1
                rows = await _recovery_rows(service, pause.session_id)
                assert len(rows) == 1 and rows[0].request.request_id == "recover-1"
                snapshots = await asyncio.to_thread(
                    lambda: list(root_a.rglob("control_plane_checkpoint_snapshot_*.json")))
                assert snapshots and all(await asyncio.gather(*(
                    asyncio.to_thread(path.is_file) for path in snapshots)))
                assert not await asyncio.to_thread((root_b / "observability").exists)
                assert not await asyncio.to_thread((root_c / "observability").exists)
                assert not await asyncio.to_thread((root_a / "agent_output/approved.txt").exists)
                record_property("epic_destination_observation", json.dumps({
                    "destinations": len(state.destinations), "transactions": state.transactions,
                    "locks": state.locks, "snapshots": len(snapshots),
                }, sort_keys=True))
            except BaseException as error:
                primary_error = error
                raise
            finally:
                await _settle(task, state, primary_error)


def _drift_reloaded_identity(monkeypatch, service):
    transaction = service.repository.transaction
    state = SimpleNamespace(transactions=0, locks=0)
    hold = service.locks.hold

    @asynccontextmanager
    async def drifted_transaction(session_id):
        async with transaction(session_id) as tx:
            state.transactions += 1
            if state.transactions == 2:
                latest = tx.approval_pauses.latest

                async def drifted_latest():
                    observed = await latest()
                    payload = json.loads(observed.model_dump_json())
                    approval_id = next(iter(payload["approvals"]))
                    payload["approvals"][approval_id]["issue_id"] = "ISSUE-DRIFT"
                    return type(observed).model_validate(payload)

                monkeypatch.setattr(tx.approval_pauses, "latest", drifted_latest)
            yield tx

    @asynccontextmanager
    async def observed_lock(session_id, *, expected=None):
        async with hold(session_id, expected=expected) as reference:
            state.locks += 1
            yield reference

    monkeypatch.setattr(service.repository, "transaction", drifted_transaction)
    monkeypatch.setattr(service.locks, "hold", observed_lock)
    return state


async def test_epic_recovery_refuses_reloaded_child_identity_without_grant_or_effect(
    tmp_path, monkeypatch,
) -> None:
    """Layer: integration. A later retained identity cannot replace captured authority."""
    async with claimed_process(tmp_path) as (child, pause):
        await _stop_child(child)
        async with approval_engine(tmp_path, monkeypatch) as engine:
            service = _approval_service(engine)
            state = _drift_reloaded_identity(monkeypatch, service)
            with pytest.raises(ValueError, match="E_EPIC_APPROVAL_IDENTITY_CONFLICT"):
                await _continue(service, pause, recovery_request(pause))
            assert state.transactions == 2 and state.locks == 1
            assert await _recovery_rows(service, pause.session_id) == []
            assert not await asyncio.to_thread(
                (tmp_path / "workspace/agent_output/approved.txt").exists)
