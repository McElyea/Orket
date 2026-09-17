from __future__ import annotations

import asyncio
import json
import os

import aiosqlite
import pytest

from orket.adapters.storage.outward_ledger_upgrade import migrate_outward_ledger_copy
from tests.helpers.outward_ledger import logical_contents, seed_ledger
from tests.helpers.outward_ledger_migration import migration_cli, seed_legacy_ledger


@pytest.mark.integration
@pytest.mark.parametrize("mutation", [
    "UPDATE run_events SET payload_json='{}' WHERE event_id='legacy:000004'",
    "UPDATE run_events SET event_hash='' WHERE event_id='legacy:000004'",
    "UPDATE run_events SET chain_hash='wrong' WHERE event_id='legacy:000004'",
    "UPDATE run_events SET turn=-1 WHERE event_id='legacy:000004'",
    "UPDATE run_events SET event_id=NULL WHERE event_id='legacy:000004'",
    "DELETE FROM outward_runs",
    "ALTER TABLE run_events ADD COLUMN unsupported TEXT",
    "CREATE TRIGGER unsupported AFTER INSERT ON run_events BEGIN SELECT 1; END",
    "DELETE FROM schema_migrations WHERE namespace='outward_run_events'",
])
# Layer: integration. Refusal preserves corrupt source evidence and rolls back the complete candidate transaction.
async def test_corrupt_legacy_copy_is_never_resealed(tmp_path, mutation):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    async with aiosqlite.connect(source) as connection:
        await connection.execute(mutation)
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, source)
    code, _, _ = await migration_cli(source, backup, destination, tmp_path / "report.json",
                                    "--writers-stopped", "--allow-unsealed")
    assert code == 1
    report = json.loads(await asyncio.to_thread((tmp_path / "report.json").read_text))
    assert report["state"] == "failed" and report["observed_result"] == "failure"
    for path in (source, backup, destination):
        assert await asyncio.to_thread(logical_contents, path) == before


@pytest.mark.integration
@pytest.mark.parametrize("mutation", [
    "DROP TABLE outward_ledger_heads_v2",
    "DROP TRIGGER outward_ledger_update_v2",
    "DELETE FROM outward_ledger_heads_v2",
    "DELETE FROM outward_ledger_commits_v2 WHERE append_sequence=2",
    "UPDATE outward_ledger_heads_v2 SET chain_hash='wrong'",
    "INSERT INTO outward_ledger_heads_v2 VALUES ('orphan', 0, 'GENESIS', 'native')",
])
# Layer: integration. Missing native metadata and damaged guards cannot be promoted to legacy import eligibility.
async def test_partial_or_corrupt_native_state_is_refused(tmp_path, mutation):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_ledger(source, 2)
    async with aiosqlite.connect(source) as connection:
        await connection.execute(mutation)
        await connection.commit()
    before = await asyncio.to_thread(logical_contents, source)
    with pytest.raises((ValueError, aiosqlite.DatabaseError)):
        await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination,
                                          writers_stopped=True, allow_unsealed=True)
    for path in (source, backup, destination):
        assert await asyncio.to_thread(logical_contents, path) == before


@pytest.mark.integration
# Layer: integration. Writer acknowledgement and exclusive new paths are prerequisites, not implicit live fencing.
async def test_copy_preconditions_preserve_all_existing_files(tmp_path):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    with pytest.raises(ValueError, match="WRITERS_MUST_BE_STOPPED"):
        await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination, writers_stopped=False)
    assert not backup.exists() and not destination.exists()
    await asyncio.to_thread(destination.write_bytes, b"preserve")
    with pytest.raises(FileExistsError):
        await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    assert await asyncio.to_thread(destination.read_bytes) == b"preserve" and not backup.exists()


@pytest.mark.integration
@pytest.mark.parametrize("hardlink", [False, True])
# Layer: integration. Report paths cannot overwrite a source database, including a distinct name for the same file.
async def test_report_collision_refused_before_any_write(tmp_path, hardlink):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    before = await asyncio.to_thread(source.read_bytes)
    report = tmp_path / "report.json" if hardlink else source
    if hardlink:
        await asyncio.to_thread(os.link, source, report)
    code, _, stderr = await migration_cli(source, backup, destination, report, "--writers-stopped")
    assert code == 2 and "REPORT_PATH_COLLISION" in stderr
    assert await asyncio.to_thread(source.read_bytes) == before
    assert not backup.exists() and not destination.exists()


@pytest.mark.integration
@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
# Layer: integration. SQLite sidecar names are protected even when the corresponding sidecar is not currently present.
async def test_sqlite_sidecar_paths_are_protected(tmp_path, suffix):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source)
    sidecar = source.with_name(source.name + suffix)
    code, _, stderr = await migration_cli(source, backup, destination, sidecar, "--writers-stopped")
    assert code == 2 and "REPORT_PATH_COLLISION" in stderr
    with pytest.raises(ValueError, match="PATH_COLLISION"):
        await migrate_outward_ledger_copy(source=source, backup=sidecar, destination=destination, writers_stopped=True)
    existing = destination.with_name(destination.name + suffix)
    await asyncio.to_thread(existing.write_bytes, b"retained-sidecar")
    with pytest.raises(FileExistsError):
        await migrate_outward_ledger_copy(source=source, backup=backup, destination=destination, writers_stopped=True)
    assert await asyncio.to_thread(existing.read_bytes) == b"retained-sidecar"
    assert not backup.exists() and not destination.exists()
