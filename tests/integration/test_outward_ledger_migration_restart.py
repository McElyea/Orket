from __future__ import annotations

import asyncio
import hashlib
import json
import sys

import pytest

from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.outward_ledger import logical_contents
from tests.helpers.outward_ledger_migration import migration_cli, seed_legacy_ledger


async def _wait_for_marker(path, process):
    async with asyncio.timeout(20):
        while not await asyncio.to_thread(path.exists):
            assert process.returncode is None, "migration worker exited before the pause"
            await asyncio.sleep(0.02)
        return int(await asyncio.to_thread(path.read_text))


@pytest.mark.integration
# Layer: integration. Kill a separate CLI process after actual uncommitted writes, then inspect and retry new copies.
async def test_interrupted_backfill_rolls_back_and_new_copy_restart_succeeds(tmp_path):
    source, backup, destination = [tmp_path / name for name in ("source.db", "backup.db", "candidate.db")]
    await seed_legacy_ledger(source, 2001)
    before = await asyncio.to_thread(logical_contents, source)
    report, reached = tmp_path / "report.json", tmp_path / "reached.txt"
    await asyncio.to_thread(write_payload_with_diff_ledger, report, {"state": "complete", "observed_result": "success"})
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.outward_ledger_migration_worker", str(reached),
        "--source", str(source), "--backup", str(backup), "--destination", str(destination),
        "--out", str(report), "--writers-stopped", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        assert await _wait_for_marker(reached, process) == 1000
        backup_digest = hashlib.sha256(await asyncio.to_thread(backup.read_bytes)).hexdigest()
        started = json.loads(await asyncio.to_thread(report.read_text))
        assert started["state"] == "started" and started["observed_result"] == "partial success"
        assert started["candidate_activated"] is False and len(started["diff_ledger"]) == 2
    finally:
        if process.returncode is None:
            process.kill()
        await asyncio.wait_for(process.communicate(), timeout=10)
    assert process.returncode != 0
    for path in (source, backup, destination):
        assert await asyncio.to_thread(logical_contents, path) == before
    assert hashlib.sha256(await asyncio.to_thread(backup.read_bytes)).hexdigest() == backup_digest
    code, _, _ = await migration_cli(source, backup, destination, report, "--writers-stopped")
    assert code == 1 and (await asyncio.to_thread(logical_contents, destination)) == before
    retry_backup, retry = tmp_path / "retry-backup.db", tmp_path / "retry.db"
    code, stdout, stderr = await migration_cli(source, retry_backup, retry, report, "--writers-stopped")
    assert code == 0, stdout + stderr
    snapshot = await OutwardLedgerSnapshotStore(retry).read("legacy")
    assert snapshot.independent_count == 2001 and snapshot.run.execution_generation == 0
    assert snapshot.anchor.origin_ref == "legacy:" + hashlib.sha256(await asyncio.to_thread(retry_backup.read_bytes)).hexdigest()
    assert json.loads(await asyncio.to_thread(report.read_text))["state"] == "complete"
