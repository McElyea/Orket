from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import replace

import aiosqlite
import pytest

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_ledger_upgrade import migrate_outward_ledger_copy
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.application.services.outward_ledger_service import OutwardLedgerService
from orket.core.domain.outward_ledger import verify_ledger_export
from tests.helpers.outward_authorization import TEST_API_KEY, FixedInputs, outward_api
from tests.helpers.outward_ledger import ledger_event, logical_contents, seed_ledger
from tests.helpers.outward_ledger_migration import migration_cli, seed_legacy_ledger, table_rows
from tests.helpers.outward_model_admission import count_calls, use_counted_model


@pytest.mark.integration
@pytest.mark.parametrize("count", [0, 4, 5001])
# Layer: integration. Real CLI migration preserves v1 exports and all source cells across multiple pages.
async def test_copied_legacy_import_preserves_evidence_and_v1_projection(tmp_path, count):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    original_export = await seed_legacy_ledger(source, count)
    export_path, report_path = tmp_path / "original-export.json", tmp_path / "report.json"
    export_bytes = (json.dumps(original_export, indent=2) + "\n").encode()
    await asyncio.to_thread(export_path.write_bytes, export_bytes)
    before = await asyncio.to_thread(logical_contents, source)
    exit_code, stdout, stderr = await migration_cli(source, backup, destination, report_path, "--writers-stopped")
    assert exit_code == 0, stdout + stderr
    report = json.loads(await asyncio.to_thread(report_path.read_text))
    backup_hash = hashlib.sha256(await asyncio.to_thread(backup.read_bytes)).hexdigest()
    assert report["backup_sha256"] == backup_hash and report["state"] == "complete"
    assert report["diff_ledger"] and report["candidate_activated"] is False
    assert report["authenticity"] == "not_established" and report["execution_authority"] == "unchanged"
    run = report["runs"][0]
    assert run["event_count"] == count and run["available_hashes_checked"] == count * 2
    assert run["anchor"]["origin_ref"] == "legacy:" + backup_hash and run["execution_generation"] == 0
    assert run["derived_v1_chain_hash"] == original_export["canonical"]["ledger_hash"]
    assert await asyncio.to_thread(logical_contents, source) == await asyncio.to_thread(logical_contents, backup) == before
    assert await table_rows(destination, "run_events") == await table_rows(source, "run_events")
    service = OutwardLedgerService(run_store=OutwardRunStore(destination), event_store=OutwardRunEventStore(destination),
                                  utc_now=lambda: "2026-09-12T12:05:00+00:00")
    migrated = await service.export("legacy")
    assert migrated["canonical"] == original_export["canonical"]
    assert verify_ledger_export(original_export)["result"] == verify_ledger_export(migrated)["result"] == "valid"
    snapshot = await OutwardLedgerSnapshotStore(destination, page_size=7).read("legacy")
    assert [event.event_id for event in snapshot.events] == [event["event_id"] for event in original_export["events"]]
    assert await asyncio.to_thread(export_path.read_bytes) == export_bytes
    assert hashlib.sha256(await asyncio.to_thread(backup.read_bytes)).hexdigest() == backup_hash


@pytest.mark.integration
# Layer: integration. A refused copy is unchanged; explicit unsealed import preserves NULL cells and reports its limits.
async def test_unsealed_history_requires_explicit_disposition_and_new_paths(tmp_path):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source, unsealed=True)
    before = await asyncio.to_thread(logical_contents, source)
    report_path = tmp_path / "report.json"
    code, _, _ = await migration_cli(source, backup, destination, report_path, "--writers-stopped")
    assert code == 1
    failed = json.loads(await asyncio.to_thread(report_path.read_text))
    assert failed["state"] == "failed" and "UNSEALED_IMPORT_ACK_REQUIRED" in failed["error"]
    assert failed["candidate_disposition"] == "unverified_do_not_activate"
    assert await asyncio.to_thread(logical_contents, destination) == before
    code, stdout, stderr = await migration_cli(source, tmp_path / "retry-backup.db", tmp_path / "retry.db", report_path,
                                               "--writers-stopped", "--allow-unsealed")
    assert code == 0, stdout + stderr
    report = json.loads(await asyncio.to_thread(report_path.read_text))
    assert report["runs"][0]["unsealed_events"] == 4 and report["runs"][0]["available_hashes_checked"] == 0
    assert len(report["diff_ledger"]) >= 4
    assert await table_rows(tmp_path / "retry.db", "run_events") == await table_rows(source, "run_events")
    assert await asyncio.to_thread(logical_contents, source) == await asyncio.to_thread(logical_contents, backup) == before


@pytest.mark.integration
# Layer: integration. Existing native anchors survive a mixed import; new appends extend the retained imported prefix.
async def test_mixed_native_and_legacy_import_preserves_authority_and_append_compatibility(tmp_path):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    await seed_ledger(source, 2)
    native = await OutwardLedgerSnapshotStore(source).read("bt2")
    report = await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    assert report["runs"][0]["disposition"] == "retained_v2" and report["runs"][0]["execution_generation"] == 1
    assert (await OutwardLedgerSnapshotStore(destination).read("bt2")).anchor == native.anchor
    legacy = await OutwardLedgerSnapshotStore(destination).read("legacy")
    assert legacy.run.execution_generation == 0 and legacy.run.status == "approval_required"
    event = replace(ledger_event(99), run_id="legacy", event_id="new-audit", event_type="ledger_export_requested")
    await OutwardRunEventStore(destination).append(event)
    after = await OutwardLedgerSnapshotStore(destination).read("legacy")
    after.compare_anchor(legacy.anchor.to_dict())
    assert after.independent_count == 5 and after.run.execution_generation == 0
    async with aiosqlite.connect(destination) as connection:
        with pytest.raises(aiosqlite.IntegrityError, match="EVENT_IMMUTABLE"):
            await connection.execute("UPDATE run_events SET payload_json='{}' WHERE run_id='legacy'")
        with pytest.raises(aiosqlite.IntegrityError, match="COMMITMENT_REQUIRED"):
            await connection.execute("""INSERT INTO run_events VALUES (
                'old-writer', 'tool_invoked', 'legacy', 1, NULL, 'now', '{}', NULL, NULL)""")


@pytest.mark.integration
# Layer: integration. SQLite backup retains committed WAL pages while the stopped writer's connection is still open.
async def test_migration_provenance_covers_committed_wal_content(tmp_path):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    async with aiosqlite.connect(source) as stopped_writer:
        await stopped_writer.execute("PRAGMA journal_mode=WAL")
        await stopped_writer.execute("PRAGMA wal_autocheckpoint=0")
        await stopped_writer.execute("UPDATE outward_runs SET stop_reason='committed-in-wal'")
        await stopped_writer.commit()
        assert await asyncio.to_thread((tmp_path / "source.db-wal").is_file)
        report = await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
        assert await table_rows(backup, "outward_runs") == await table_rows(source, "outward_runs")
        assert (await OutwardRunStore(destination).get("legacy")).stop_reason == "committed-in-wal"
        assert report["backup_sha256"] == hashlib.sha256(await asyncio.to_thread(backup.read_bytes)).hexdigest()


@pytest.mark.integration
# Layer: integration. Real authenticated reentry cannot turn imported legacy evidence into current dispatch permission.
async def test_imported_legacy_run_stays_quarantined_through_api_restart(tmp_path, monkeypatch):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source, unsealed=True)
    await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination,
                                      writers_stopped=True, allow_unsealed=True)
    monkeypatch.setenv("ORKET_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ORKET_OUTWARD_PIPELINE_DB_PATH", str(destination))
    use_counted_model(monkeypatch, tmp_path, [{"tool": "write_file", "args": {"path": "forbidden.txt", "content": "bad"}}])
    before = await table_rows(destination, "run_events")
    for _restart in range(2):
        async with outward_api(tmp_path, FixedInputs()) as (client, context):
            response = await client.post("/v1/runs", json={
                "run_id": "legacy", "task": {"description": "new task", "instruction": "write forbidden.txt"},
            })
            assert response.status_code == 409 and response.json()["detail"] == "E_OUTWARD_LEGACY_RUN_QUARANTINED"
            with pytest.raises(RuntimeError, match="E_OUTWARD_LEGACY_RUN_QUARANTINED"):
                await context.outward_run_execution_service.start_if_ready("legacy")
            verification = await client.get("/v1/runs/legacy/ledger/verify")
            assert verification.status_code == 200 and verification.json()["retained_integrity"] == "valid"
    assert await count_calls(tmp_path) == 0 and not await asyncio.to_thread((tmp_path / "forbidden.txt").exists)
    assert await table_rows(destination, "run_events") == before
