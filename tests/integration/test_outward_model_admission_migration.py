"""Layer: integration. Copied v1 admission migration with real legacy-layout model artifacts."""

from __future__ import annotations

import asyncio
import sqlite3
from dataclasses import asdict, replace

import pytest

from orket.adapters.storage.outward_model_admission_migrations import OUTWARD_MODEL_ADMISSION_MIGRATIONS
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.sqlite_connection import connect_sqlite_wal
from orket.adapters.storage.sqlite_migrations import SQLiteMigrationRunner
from orket.adapters.tools.registry import DEFAULT_BUILTIN_CONNECTOR_REGISTRY
from orket.application.services.outward_authority_migration_service import OutwardAuthorityMigrationService
from orket.application.services.outward_model_tool_call_service import OutwardModelToolCallService
from orket.application.services.outward_run_lifecycle import turn_started_event
from orket.application.services.outward_run_service import OutwardRunService
from orket.core.domain.outward_authorization import canonical_json
from orket.core.domain.outward_model_admission import admission_digest
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord
from tests.helpers.outward_authorization import approve, outward_api
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.outward_effect_worker import CountedModelClient
from tests.helpers.outward_model_admission import (
    admission_snapshot,
    count_calls,
    retry_run,
    use_counted_model,
)


def _artifact_snapshot(root):
    return {path: path.read_bytes() for path in root.rglob("*.json")}


async def legacy_queued(db_path, inputs, calls):
    """Seed pre-cutover admission without initializing today's model/control-plane schemas."""
    run = OutwardRunRecord(
        run_id="bt0-run", namespace="issue:bt0-run", status="queued", current_turn=0, max_turns=len(calls),
        submitted_at=inputs.utc_now_iso(), execution_generation=1,
        task={"description": "Legacy model admission", "instruction": "Write each approved file.",
              "acceptance_contract": {"governed_tool_sequence": calls}},
        policy_overrides={"approval_required_tools": ["write_file"], "max_turns": len(calls)},
    )
    await OutwardRunStore(db_path).create(run)
    await OutwardRunEventStore(db_path).append(OutwardRunService._initial_event(run))
    return run


async def legacy_fixture(db_path, root, queued, calls, *, observed):
    """Seed the frozen v1 contract; produce its evidence through the actual legacy-layout model service."""
    started = replace(queued, status="running", current_turn=1, started_at=queued.submitted_at)
    await OutwardRunStore(db_path).update(started)
    events = OutwardRunEventStore(db_path)
    await events.append(LedgerEvent(
        event_id=f"run:{queued.run_id}:0100:started", event_type="run_started", run_id=queued.run_id,
        turn=0, agent_id="outward-agent", at=queued.submitted_at,
        payload={"run_id": queued.run_id, "status": "running", "started_at": queued.submitted_at},
    ))
    await events.append(turn_started_event(started, at=queued.submitted_at))
    inputs = canonical_json(asdict(started))
    async with connect_sqlite_wal(db_path) as connection:
        await SQLiteMigrationRunner(namespace="outward_model_admissions").apply(connection, OUTWARD_MODEL_ADMISSION_MIGRATIONS[:1])
        await connection.execute("""INSERT INTO outward_model_admissions
            (run_id, execution_generation, turn, step_index, inputs_json, inputs_digest, state, created_at)
            VALUES (?, 1, 1, 0, ?, ?, 'ready', ?)""", (queued.run_id, inputs, admission_digest(inputs), queued.submitted_at))
        await connection.execute("UPDATE outward_model_admissions SET state = 'claimed', owner_id = 'legacy-model-owner', claimed_at = ?",
                                 (queued.submitted_at,))
        await connection.commit()
    model = OutwardModelToolCallService(connector_registry=DEFAULT_BUILTIN_CONNECTOR_REGISTRY, workspace_root=root,
                                        model_client_factory=lambda: CountedModelClient(root, calls))
    result = await model.produce_governed_tool_call(run=started, expected_tool="write_file", governed_tools={"write_file"})
    if observed:
        payload = canonical_json({"tool_call": result.tool_call, "model_invocation": result.model_invocation})
        async with connect_sqlite_wal(db_path) as connection:
            await connection.execute("""UPDATE outward_model_admissions SET state = 'observed',
                result_json = ?, result_digest = ?, observed_at = ?""", (payload, admission_digest(payload), queued.submitted_at))
            await connection.commit()
    return result.model_invocation


async def legacy_row(db_path):
    async with connect_sqlite_wal(db_path) as connection:
        cursor = await connection.execute("SELECT * FROM outward_model_admissions")
        row = await cursor.fetchone()
        return dict(zip([column[0] for column in cursor.description], row, strict=True))


@pytest.mark.integration
@pytest.mark.parametrize("observed", [False, True])
@pytest.mark.parametrize("interrupt_migration", [False, True])
# Layer: integration
async def test_copied_legacy_model_admission_retains_artifacts_and_rolls_forward(tmp_path, boundary, monkeypatch, observed, interrupt_migration):
    """The old copy and its evidence stay unchanged; migration rollback retains v1 until an actual retry succeeds."""
    source, inputs, calls = boundary
    calls = calls[:1]
    queued = await legacy_queued(source, inputs, calls)
    evidence = await legacy_fixture(source, tmp_path, queued, calls, observed=observed)
    original = await legacy_row(source)
    original_files = await asyncio.to_thread(_artifact_snapshot, tmp_path / "workspace")
    destination = tmp_path / "copied-model.sqlite3"
    async with connect_sqlite_wal(source) as source_connection, connect_sqlite_wal(destination) as destination_connection:
        await source_connection.backup(destination_connection)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(destination))
    use_counted_model(monkeypatch, tmp_path, calls)
    if interrupt_migration:
        async with connect_sqlite_wal(destination) as connection:
            await connection.execute("""CREATE TRIGGER reject_model_migration BEFORE INSERT ON schema_migrations
                WHEN NEW.namespace = 'outward_model_admissions' AND NEW.version = 2
                BEGIN SELECT RAISE(ABORT, 'test migration failure'); END""")
            await connection.commit()
        async with outward_api(tmp_path, inputs) as (client, _context):
            assert (await client.get("/v1/runs/bt0-run/model-admission")).status_code == 500
        assert await legacy_row(destination) == original
        async with connect_sqlite_wal(destination) as connection:
            assert await (await connection.execute("SELECT name FROM sqlite_master WHERE name = 'outward_model_attempts_v2'")).fetchone() is None
            await connection.execute("DROP TRIGGER reject_model_migration")
            await connection.commit()
    async with outward_api(tmp_path, inputs) as (client, _context):
        inspected = await client.get("/v1/runs/bt0-run/model-admission")
        assert inspected.status_code == 200, inspected.text
        migrated = await admission_snapshot(destination)
        assert {key: asdict(migrated)[key] for key in original} == original
        assert migrated.evidence_layout_version == 1
        authority = OutwardAuthorityMigrationService(destination, runtime_inputs=inputs)
        inspected_authority = await authority.inspect(queued.run_id)
        await authority.migrate(queued.run_id, expected_run_digest=inspected_authority["expected_run_digest"],
                                actor_ref="legacy-model-migration-test", owners_stopped=True)
        if not observed:
            response = await client.post("/v1/runs/bt0-run/model-admission/recover", json={
                "request_id": "migrated-model", "execution_generation": 1, "turn": 1, "step_index": 0,
                "expected_owner_id": migrated.owner_id, "expected_fencing_generation": 1,
            })
            assert response.status_code == 200 and response.json()["admission"]["evidence_layout_version"] == 2
        response = await retry_run(client, queued)
        assert response.status_code == 200 and response.json()["status"] == "approval_required", response.text
        assert (await approve(client, response.json()["pending_proposals"][0]["proposal_id"])).status_code == 200
    async with connect_sqlite_wal(destination) as connection:
        with pytest.raises(sqlite3.OperationalError, match="no such table"):
            await connection.execute("UPDATE outward_model_admissions SET state = 'observed'")
    assert await legacy_row(source) == original
    for path, contents in original_files.items():
        assert await asyncio.to_thread(path.read_bytes) == contents
    assert tmp_path / evidence["model_invocation_ref"] in original_files
    assert await count_calls(tmp_path) == (1 if observed else 2)
    assert await asyncio.to_thread((tmp_path / "first.txt").read_text) == calls[0]["args"]["content"]
