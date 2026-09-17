"""Offline, atomic adoption of a reviewed generation-one outward history."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from pathlib import Path

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.application.services.control_plane_snapshot_publication import snapshot_digest
from orket.application.services.outward_authority_migration_evidence import migration_evidence
from orket.application.services.outward_control_plane_service import (
    OUTWARD_AUTHORITY_ADOPTION_EVENT,
    admission_configuration,
    admit_outward_run,
    authority_adoption_event_id,
    begin_outward_execution,
    outward_status_payload,
    require_outward_authority,
)
from orket.application.services.outward_terminal_service import publish_outward_terminal
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.domain.outward_run_events import LedgerEvent


class OutwardAuthorityMigrationService:
    def __init__(self, db_path: Path, *, runtime_inputs: RuntimeInputService | None = None):
        self.db_path = db_path
        self.inputs = runtime_inputs or RuntimeInputService()
        self.ledger = OutwardLedgerSnapshotStore(db_path)
        self.unit = OutwardStoreUnitOfWork.for_run_stores(OutwardRunStore(db_path), OutwardRunEventStore(db_path))

    async def inspect(self, run_id: str) -> dict:
        snapshot = await self.ledger.read(run_id)
        return {"run_id": run_id, "status": snapshot.run.status, "execution_generation": snapshot.run.execution_generation,
                "expected_run_digest": snapshot_digest(asdict(snapshot.run)), "ledger_anchor": snapshot.anchor.to_dict(),
                "input_basis": "current retained row; original instruction authenticity is not established"}

    async def migrate(self, run_id: str, *, expected_run_digest: str, actor_ref: str, owners_stopped: bool) -> dict:
        if owners_stopped is not True:
            raise ValueError("E_OUTWARD_MIGRATION_OFFLINE_REQUIRED")
        if not actor_ref.strip() or not expected_run_digest.strip():
            raise ValueError("E_OUTWARD_MIGRATION_REVIEW_REQUIRED")
        if not await asyncio.to_thread(self.db_path.is_file):
            raise ValueError("E_OUTWARD_MIGRATION_DATABASE_MISSING")
        async with self.unit.transaction() as transaction:
            # Validate the ledger through the owning writer transaction, including its schema migrations.
            snapshot = await transaction.ledger.read(run_id)
            run = snapshot.run
            run.require_execution_admission()
            adoption = await transaction.get_event(authority_adoption_event_id(run_id))
            if adoption is not None:
                return await self._existing(transaction, snapshot, adoption, expected_run_digest, actor_ref)
            if snapshot_digest(asdict(run)) != expected_run_digest:
                raise RuntimeError("E_OUTWARD_MIGRATION_REVIEWED_STATE_CHANGED")
            basis = await migration_evidence(transaction, snapshot)
            at = self.inputs.utc_now_iso()
            adoption = await transaction.append_event(LedgerEvent(
                event_id=authority_adoption_event_id(run_id), event_type=OUTWARD_AUTHORITY_ADOPTION_EVENT,
                run_id=run_id, turn=run.current_turn, agent_id="operator", at=at,
                payload={"actor_ref": actor_ref, "reviewed_run_digest": expected_run_digest,
                         "historical_anchor": snapshot.anchor.to_dict(), "input_basis": "reviewed_current_state",
                         "configuration_digest": snapshot_digest(admission_configuration(run)),
                         "policy_digest": snapshot_digest(run.policy_overrides), "owners_stopped_attestation": True},
            ))
            await admit_outward_run(transaction, run, adoption=adoption)
            if run.status != "queued":
                await begin_outward_execution(transaction, run)
            if basis is not None:
                outcome, cause = basis
                await publish_outward_terminal(transaction, run, at=at, outcome=outcome, reason=run.stop_reason,
                                               cause=cause, adoption=adoption)
            return await outward_status_payload(transaction, run)

    async def _existing(self, transaction, snapshot, adoption, expected_run_digest, actor_ref):
        if (adoption.event_type != OUTWARD_AUTHORITY_ADOPTION_EVENT
                or adoption.payload.get("actor_ref") != actor_ref
                or adoption.payload.get("reviewed_run_digest") != expected_run_digest):
            raise RuntimeError("E_OUTWARD_MIGRATION_ADOPTION_CONFLICT")
        snapshot.compare_anchor(adoption.payload["historical_anchor"])
        await require_outward_authority(transaction, snapshot.run)
        return await outward_status_payload(transaction, snapshot.run)
