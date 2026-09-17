"""Layer: integration. Real journal, checkpoint replay, process ownership and fixture provider."""
from __future__ import annotations

import asyncio
import hashlib
import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite
import pytest

from orket.adapters.storage.epic_publication_repository import SQLiteEpicPublicationRepository
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.core.contracts.epic_approval_recovery import EPIC_APPROVAL_RECOVERY_ARTIFACT
from tests.integration.test_epic_approval_continuation import approval_engine
from tests.integration.test_epic_closeout_process import read_barrier

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


def recovery_request(pause, **changes):
    return {"session_id": pause.session_id, "sequence": pause.sequence, "request_id": "recover-1",
            "expected_pause_digest": pause.digest(), "expected_recovery_digest": None,
            "operator_ref": "fixture-operator", "reason_ref": "fixture-process-interrupted",
            "resolution": "continue_resolved_pause", **changes}


async def reenter(engine, request=None):
    return await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build",
                                 approval_recovery=request)


@asynccontextmanager
async def claimed_process(root, decision="approve", stage="claimed"):
    child = await asyncio.create_subprocess_exec(
        sys.executable, str(ROOT / "tests/helpers/epic_approval_recovery_worker.py"), str(root), decision, stage,
        env={**os.environ, "PYTHONPATH": str(ROOT), "ORKET_DISABLE_SANDBOX": "1"},
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        barrier = await asyncio.wait_for(read_barrier(child), 60)
        async with SQLiteEpicPublicationRepository(Path(barrier["runtime_db"])).transaction("approval-session") as tx:
            pause = await tx.approval_pauses.latest()
            assert pause.digest() == barrier["pause_digest"]
        yield child, pause
    finally:
        if child.returncode is None:
            child.kill()
        await asyncio.wait_for(child.communicate(), 15)


def receipt_hashes(workspace):
    return {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in workspace.rglob("model_response_raw.json")}


@pytest.mark.parametrize("decision", ["approve", "deny"])
# Layer: integration
async def test_dead_approval_owner_recovers_original_pause_once(tmp_path, monkeypatch, decision):
    async with claimed_process(tmp_path, decision) as (child, pause):
        before = await asyncio.to_thread(receipt_hashes, tmp_path / "workspace")
        assert before and child.returncode is None
        async with approval_engine(tmp_path, monkeypatch) as engine:
            request = recovery_request(pause)
            busy = await reenter(engine, request)
            assert busy.observation == "unresolved" and "owner_busy" in busy.reason
            child.kill()
            await asyncio.wait_for(child.communicate(), 15)
            ordinary = await reenter(engine)
            assert ordinary.observation == "unresolved" and "CONTINUATION_UNCERTAIN" in ordinary.reason
            result = await reenter(engine, request)
            assert result.observation == "published" and result.succeeded is (decision == "approve")
            journal = engine._pipeline.epic_publication.repository
            async with journal.transaction(pause.session_id) as tx:
                assert await tx.approval_pauses.latest() == pause
                records = await tx.approval_pauses.recoveries()
                assert len(records) == 1 and records[0].request.request_id == request["request_id"]
                assert (await tx.get_outcome()).artifacts[EPIC_APPROVAL_RECOVERY_ARTIFACT] == [records[0].reference()]
                assert (await tx.get_admission()).phase == "released"
            output = tmp_path / "workspace/agent_output/approved.txt"
            assert await asyncio.to_thread(output.exists) is (decision == "approve")
            if decision == "approve":
                assert await asyncio.to_thread(output.read_text, encoding="utf-8") == "approved"
            after = await asyncio.to_thread(receipt_hashes, tmp_path / "workspace")
            assert all(after[path] == digest for path, digest in before.items())
            assert (await reenter(engine, request)).model_dump() == result.model_dump()
            assert await asyncio.to_thread(receipt_hashes, tmp_path / "workspace") == after
            conflict = await reenter(engine, {**request, "reason_ref": "changed"})
            assert conflict.observation == "unresolved" and "REQUEST_CONFLICT" in conflict.reason


@pytest.mark.parametrize("damage", ["snapshot", "orphan", "unmarked", "head", "acceptance"])
# Layer: integration
async def test_recovery_refuses_missing_authority_without_grant(tmp_path, monkeypatch, damage):
    async with claimed_process(tmp_path) as (child, pause):
        child.kill()
        await asyncio.wait_for(child.communicate(), 15)
        async with approval_engine(tmp_path, monkeypatch) as engine:
            request = recovery_request(pause)
            journal = engine._pipeline.epic_publication.repository
            identity = next(iter(pause.approvals.values()))
            directory = TurnArtifactWriter(tmp_path / "workspace")._turn_output_dir(
                session_id=pause.session_id, issue_id=identity["issue_id"], role_name=identity["seat_name"],
                turn_index=identity["payload_json"]["turn_index"])
            if damage == "snapshot":
                snapshots = await asyncio.to_thread(lambda: list(directory.glob("control_plane_checkpoint_snapshot_*.json")))
                assert len(snapshots) == 1
                await asyncio.to_thread(snapshots[0].rename, snapshots[0].with_suffix(".preserved"))
            elif damage == "orphan":
                operations = directory / "operations"
                await asyncio.to_thread(operations.mkdir, exist_ok=True)
                await asyncio.to_thread((operations / "orphan.json").write_text, "{}", encoding="utf-8")
            elif damage == "unmarked":
                artifacts = {key: value for key, value in pause.artifacts.items() if key != "epic_continuation_lock"}
                pause = pause.model_copy(update={"artifacts": artifacts})
                async with aiosqlite.connect(journal.db_path) as connection:
                    await connection.execute("UPDATE epic_approval_pauses SET payload=?, digest=?",
                                             (pause.model_dump_json(), pause.digest()))
                    await connection.commit()
                request = recovery_request(pause)
            elif damage == "head":
                request["expected_recovery_digest"] = "0" * 64
            else:
                async with aiosqlite.connect(engine.control_plane_repository.db_path) as connection:
                    await connection.execute("DELETE FROM checkpoint_acceptance_records")
                    await connection.commit()
            result = await reenter(engine, request)
            assert result.observation == "unresolved" and not result.succeeded
            async with journal.transaction(pause.session_id) as tx:
                assert await tx.approval_pauses.recoveries() == []
                assert await tx.get_outcome() is None and await tx.get() is None
                assert await tx.approval_pauses.latest() == pause
            assert not await asyncio.to_thread((tmp_path / "workspace/agent_output/approved.txt").exists)
