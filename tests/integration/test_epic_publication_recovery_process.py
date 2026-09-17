"""Independent process restart preserves accepted work across publication gaps."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import aiosqlite
import pytest

from tests.integration.test_epic_closeout_process import read_barrier

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


async def launch(root, workspace, db_path, mode, stage, *, recovery=None, export_recovery=None):
    return await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "tests/helpers/epic_publication_recovery_worker.py"),
        str(root), str(workspace), str(db_path), mode, stage,
        env={**os.environ, "PYTHONPATH": str(ROOT), "ORKET_DISABLE_SANDBOX": "1",
             "ORKET_TEST_EPIC_RECOVERY": json.dumps(recovery), "ORKET_TEST_EPIC_EXPORT_RECOVERY": json.dumps(export_recovery)},
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)


async def retained_rows(db_path):
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        rows = {}
        for table in ("run_ledger", "sessions", "session_snapshots", "success_ledger"):
            exists = await (await conn.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,))).fetchone()
            if exists:
                rows[table] = [dict(row) for row in await (await conn.execute(f"SELECT * FROM {table}")).fetchall()]
        return rows


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["outcome", "closeout", "receipts", "summary", "export", "ledger", "session", "snapshot", "success"])
# Layer: integration
async def test_native_restart_after_effect_commit_preserves_history(test_root, workspace, db_path, stage):
    child = await launch(test_root, workspace, db_path, "kill", stage)
    resumed = []
    try:
        await asyncio.wait_for(read_barrier(child), timeout=40)
        assert child.returncode is None
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
        before = await retained_rows(db_path)
        resumed = [await launch(test_root, workspace, db_path, "resume", stage) for _ in range(2)]
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=50)
        for process, (stdout, stderr) in zip(resumed, replies, strict=True):
            assert process.returncode == 0, stderr.decode(errors="replace")
            assert json.loads(stdout.splitlines()[-1])["status"] == "done"
        after = await retained_rows(db_path)
        published_tables = ("run_ledger", "sessions", "session_snapshots", "success_ledger")
        effect_stages = ("ledger", "session", "snapshot", "success")
        last_published = effect_stages.index(stage) if stage in effect_stages else -1
        for table, rows in before.items():
            # Only effects already published at the barrier must remain byte-for-byte equivalent.
            if published_tables.index(table) <= last_published:
                assert after[table] == rows, table
        assert after["sessions"][0]["status"] == "done"
        assert len(after["session_snapshots"]) == len(after["success_ledger"]) == 1
    finally:
        for process in [child, *resumed]:
            if process.returncode is None:
                process.kill()
            await process.communicate()


@pytest.mark.asyncio
# Layer: integration
async def test_export_effect_without_receipt_is_not_repeated_on_native_reentry(test_root, workspace, db_path):
    child = await launch(test_root, workspace, db_path, "kill", "export_uncertain")
    resumed = []
    try:
        await asyncio.wait_for(read_barrier(child), timeout=40)
        child.kill()
        await asyncio.wait_for(child.communicate(), timeout=10)
        marker = workspace / "export-effect.txt"
        before = await asyncio.to_thread(marker.read_bytes)
        rows = await retained_rows(db_path)
        resumed = [await launch(test_root, workspace, db_path, "resume", "export_uncertain") for _ in range(2)]
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=40)
        for process, (_stdout, stderr) in zip(resumed, replies, strict=True):
            assert process.returncode != 0
            assert "E_EPIC_EXPORT_OUTCOME_UNCERTAIN" in stderr.decode(errors="replace")
        assert await asyncio.to_thread(marker.read_bytes) == before
        assert await retained_rows(db_path) == rows
        assert rows["run_ledger"][0]["status"] == "running"
        assert rows.get("success_ledger", []) == []
    finally:
        for process in [child, *resumed]:
            if process.returncode is None:
                process.kill()
            await process.communicate()
