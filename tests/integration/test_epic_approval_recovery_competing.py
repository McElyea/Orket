"""Layer: integration. Independent native callers contend for one retained continuation."""
from __future__ import annotations

import asyncio
import json
import os
import sys

import pytest

from tests.integration.test_epic_approval_continuation import approval_engine
from tests.integration.test_epic_approval_recovery import ROOT, claimed_process, recovery_request
from tests.integration.test_epic_closeout_process import read_barrier

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_independent_recovery_callers_cannot_both_gain_dispatch(tmp_path, monkeypatch):
    async with claimed_process(tmp_path) as (previous, pause):
        previous.kill()
        await asyncio.wait_for(previous.communicate(), 15)
        children = []
        try:
            for request_id in ("caller-1", "caller-2"):
                child = await asyncio.create_subprocess_exec(
                    sys.executable, str(ROOT / "tests/helpers/epic_approval_recovery_worker.py"), "recover", str(tmp_path),
                    json.dumps(recovery_request(pause, request_id=request_id)),
                    env={**os.environ, "PYTHONPATH": str(ROOT), "ORKET_DISABLE_SANDBOX": "1"},
                    stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                children.append(child)
                assert (await asyncio.wait_for(read_barrier(child), 60))["barrier"] == "recovery_caller_ready"
            results = await asyncio.wait_for(asyncio.gather(*(child.communicate(b"recover\n") for child in children)), 60)
            observations = []
            for child, (stdout, stderr) in zip(children, results, strict=True):
                assert child.returncode == 0, stderr.decode(errors="replace")
                lines = [json.loads(line) for line in stdout.decode().splitlines() if line.startswith('{"result"')]
                assert len(lines) == 1
                observations.append(lines[0])
            assert sum(row["succeeded"] for row in observations) == 1
            assert sorted(row["result"] for row in observations) == ["published", "unresolved"]
            async with approval_engine(tmp_path, monkeypatch) as engine:
                async with engine._pipeline.epic_publication.repository.transaction(pause.session_id) as tx:
                    records = await tx.approval_pauses.recoveries()
                    assert len(records) == 1 and await tx.approval_pauses.latest() == pause
                    assert (await tx.get_admission()).phase == "released"
                target = next(iter(pause.approvals.values()))["payload_json"]["control_plane_target_ref"]
                effects = await engine.control_plane_repository.list_effect_journal_entries(run_id=target)
                assert effects
                assert await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").read_text,
                                               encoding="utf-8") == "approved"
        finally:
            for child in children:
                if child.returncode is None:
                    child.kill()
                await asyncio.wait_for(child.communicate(), 15)
