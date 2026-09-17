"""Native death before adoption commit leaves history available for explicit retry."""

from __future__ import annotations

import asyncio
import sys

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from tests.integration.test_outward_authority_migration import legacy_queued


@pytest.mark.integration
@pytest.mark.asyncio
# Layer: integration
async def test_native_death_rolls_back_outward_authority_adoption(tmp_path):
    db, run, service = await legacy_queued(tmp_path)
    before = await OutwardLedgerSnapshotStore(db).read(run.run_id)
    inspection = await service.inspect(run.run_id)
    marker = tmp_path / "adoption-uncommitted"
    process = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "tests.helpers.outward_authority_migration_worker", str(db), run.run_id,
        inspection["expected_run_digest"], str(marker), "outward_authority_adopted",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    try:
        async with asyncio.timeout(20):
            while not await asyncio.to_thread(marker.exists):
                assert process.returncode is None, (await process.communicate())[1].decode(errors="replace")
                await asyncio.sleep(0.01)
        process.kill()
        await process.wait()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        await process.communicate()
    assert process.returncode != 0
    assert await OutwardLedgerSnapshotStore(db).read(run.run_id) == before
    assert await AsyncControlPlaneExecutionRepository(db).get_run_record(run_id=run.run_id) is None
    result = await service.migrate(run.run_id, expected_run_digest=inspection["expected_run_digest"],
                                   actor_ref="native-migration-proof", owners_stopped=True)
    assert result["authority_state"] == "shared" and result["final_truth"] is None
