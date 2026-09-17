"""Offline adoption binds reviewed inputs atomically and preserves retained history."""

from __future__ import annotations

from dataclasses import asdict, replace

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.application.services.outward_authority_migration_service import OutwardAuthorityMigrationService
from orket.application.services.outward_control_plane_service import authority_adoption_event_id
from orket.application.services.outward_run_service import OutwardRunService
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.outward_authorization import FixedInputs

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def legacy_queued(tmp_path):
    db = tmp_path / "legacy.sqlite3"
    run = OutwardRunRecord(run_id="legacy", namespace="issue:legacy", status="queued", current_turn=0, max_turns=20,
                          submitted_at=FixedInputs().utc_now_iso(), task={"description": "old", "instruction": "review current inputs"},
                          policy_overrides={}, execution_generation=1)
    await OutwardRunStore(db).create(run)
    await OutwardRunEventStore(db).append(OutwardRunService._initial_event(run))
    return db, run, OutwardAuthorityMigrationService(db, runtime_inputs=FixedInputs())


# Layer: integration
async def test_migration_preserves_native_rows_and_is_idempotent(tmp_path):
    db, run, service = await legacy_queued(tmp_path)
    inspection = await service.inspect(run.run_id)
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    arguments = dict(expected_run_digest=inspection["expected_run_digest"], actor_ref="local-operator", owners_stopped=True)
    result = await service.migrate(run.run_id, **arguments)
    assert result["authority_state"] == "shared" and result["final_truth"] is None
    assert await service.migrate(run.run_id, **arguments) == result
    after = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    assert after.run == run and after.events[:-1] == before.events
    assert after.events[-1].event_id == authority_adoption_event_id(run.run_id)
    assert after.events[-1].payload["input_basis"] == "reviewed_current_state"
    after.compare_anchor(before.anchor.to_dict())
    shared = await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=run.run_id)
    assert shared.admission_decision_receipt_ref == after.events[-1].event_id
    assert shared.current_attempt_id == "outward:legacy:generation:1"


@pytest.mark.parametrize("refusal", ["owners_running", "stale_digest", "generation_zero"])
# Layer: integration
async def test_migration_refuses_unreviewed_or_quarantined_history(tmp_path, refusal):
    db, run, service = await legacy_queued(tmp_path)
    digest = snapshot_digest(asdict(run))
    if refusal == "generation_zero":
        run = replace(run, execution_generation=0)
        await OutwardRunStore(db).update(run)
        digest = snapshot_digest(asdict(run))
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    with pytest.raises((ValueError, RuntimeError), match="E_OUTWARD_"):
        await service.migrate(run.run_id, expected_run_digest="sha256:stale" if refusal == "stale_digest" else digest,
                              actor_ref="local-operator", owners_stopped=refusal != "owners_running")
    after = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    assert after == before
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=run.run_id) is None


# Layer: integration
async def test_migration_failure_rolls_back_adoption_and_shared_admission(tmp_path, monkeypatch):
    db, run, service = await legacy_queued(tmp_path)
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)

    async def interrupt(*args, **kwargs):
        raise RuntimeError("injected migration interruption")

    arguments = dict(expected_run_digest=snapshot_digest(asdict(run)), actor_ref="local-operator", owners_stopped=True)
    with monkeypatch.context() as patch:
        patch.setattr(AsyncControlPlaneExecutionRepository, "save_attempt_record", interrupt)
        with pytest.raises(RuntimeError, match="injected migration interruption"):
            await service.migrate(run.run_id, **arguments)
    assert await OutwardLedgerSnapshotStore(db).read(run.run_id) == before
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=run.run_id) is None
    assert (await service.migrate(run.run_id, **arguments))["authority_state"] == "shared"
