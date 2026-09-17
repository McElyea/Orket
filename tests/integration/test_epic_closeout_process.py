"""Independent process interruption and reentry observe committed closeout truth."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.async_repositories import AsyncSessionRepository
from orket.core.domain import AttemptState, RunState

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "tests/helpers/epic_publication_worker.py"


async def worker(test_root, workspace, db_path, mode):
    env = {**os.environ, "ORKET_DISABLE_SANDBOX": "1", "PYTHONPATH": str(ROOT)}
    return await asyncio.create_subprocess_exec(sys.executable, str(WORKER), str(test_root), str(workspace),
        str(db_path), mode, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env)


async def read_barrier(process):
    while True:
        line = await process.stdout.readline()
        if not line:
            raise AssertionError((await process.stderr.read()).decode(errors="replace"))
        if line.startswith(b'{"barrier"'):
            return json.loads(line)


@pytest.mark.asyncio
@pytest.mark.parametrize("stage", ["before_commit", "after_commit"])
# Layer: integration
async def test_killed_closeout_is_atomic_and_concurrent_reentry_reuses_committed_truth(test_root, workspace, db_path, stage):
    process = await worker(test_root, workspace, db_path, stage)
    resumed = []
    try:
        marker = await asyncio.wait_for(read_barrier(process), timeout=40)
        assert process.returncode is None
        process.kill()
        await asyncio.wait_for(process.communicate(), timeout=10)
        execution = AsyncControlPlaneExecutionRepository(marker["cp_db"])
        records = AsyncControlPlaneRecordRepository(marker["cp_db"])
        run = await execution.get_run_record(run_id=marker["run_id"])
        attempt = await execution.get_attempt_record(attempt_id=run.current_attempt_id)
        expected_run = RunState.EXECUTING if stage == "before_commit" else RunState.COMPLETED
        expected_attempt = AttemptState.EXECUTING if stage == "before_commit" else AttemptState.COMPLETED
        assert run.lifecycle_state == expected_run and attempt.attempt_state == expected_attempt
        truth = await records.get_final_truth(run_id=run.run_id)
        assert (truth is not None) is (stage == "after_commit")
        assert (await AsyncSessionRepository(db_path).get_session("publication-session"))["status"] != "done"
        resumed = [await worker(test_root, workspace, db_path, "resume") for _ in range(2)]
        replies = await asyncio.wait_for(asyncio.gather(*(p.communicate() for p in resumed)), timeout=40)
        for child, (stdout, stderr) in zip(resumed, replies, strict=True):
            assert child.returncode == 0, stderr.decode(errors="replace")
            assert json.loads(stdout.splitlines()[-1])["state"] == "completed"
        final = await records.get_final_truth(run_id=run.run_id)
        assert final is not None
        if truth is not None:
            assert final == truth
        entries = await records.list_effect_journal_entries(run_id=run.run_id)
        assert len(entries) == 2
        # This is closeout reentry only; it does not silently rerun work or finish other stores.
        assert (await AsyncSessionRepository(db_path).get_session("publication-session"))["status"] != "done"
    finally:
        for child in [process, *resumed]:
            if child.returncode is None:
                child.kill()
            await child.communicate()
