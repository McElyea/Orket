"""Layer: integration. Interrupted grants cannot authorize another automatic dispatch."""
from __future__ import annotations

import asyncio

import aiosqlite
import pytest

from orket.adapters.storage.epic_continuation_lock import EpicContinuationLocks
from orket.core.contracts.epic_approval_recovery import EpicContinuationLockRef
from orket.runtime.execution import epic_run_result_boundary as boundary
from orket.runtime.execution.epic_run_finalize import EpicRunFinalizer
from tests.integration.test_epic_approval_continuation import approval_engine
from tests.integration.test_epic_approval_recovery import claimed_process, recovery_request, reenter

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Layer: integration
async def test_completed_child_does_not_grant_pre_effect_recovery(tmp_path, monkeypatch):
    async with claimed_process(tmp_path, stage="post_effect") as (child, pause):
        child.kill()
        await asyncio.wait_for(child.communicate(), 15)
        output = tmp_path / "workspace/agent_output/approved.txt"
        assert await asyncio.to_thread(output.read_text, encoding="utf-8") == "approved"
        async with approval_engine(tmp_path, monkeypatch) as engine:
            result = await reenter(engine, recovery_request(pause))
            assert result.observation == "unresolved" and "RECOVERY_POST_EFFECT" in result.reason
            async with engine._pipeline.epic_publication.repository.transaction(pause.session_id) as tx:
                assert await tx.approval_pauses.recoveries() == []
                assert await tx.get_outcome() is None and await tx.get() is None
            assert await asyncio.to_thread(output.read_text, encoding="utf-8") == "approved"


# Layer: integration
async def test_interrupted_grant_needs_new_head_and_retains_outcome_before_unlock(tmp_path, monkeypatch):
    async with claimed_process(tmp_path) as (child, pause):
        child.kill()
        await asyncio.wait_for(child.communicate(), 15)
        async with approval_engine(tmp_path, monkeypatch) as engine:
            request = recovery_request(pause)
            calls, boundaries = [], []
            restore = boundary.restore_approval_context

            async def interrupted(*args):
                calls.append("restore")
                raise OSError("fixture interruption after recovery grant")

            monkeypatch.setattr(boundary, "restore_approval_context", interrupted)
            result = await reenter(engine, request)
            assert result.observation == "unresolved" and "fixture interruption" in result.reason
            journal = engine._pipeline.epic_publication.repository
            async with journal.transaction(pause.session_id) as tx:
                records = await tx.approval_pauses.recoveries()
                assert len(records) == 1 and await tx.get_outcome() is None
            observed = await reenter(engine, request)
            assert "grant_already_consumed" in observed.reason
            assert f"epic-approval-recovery:{pause.session_id}:sha256:{records[0].digest()}" in observed.evidence_refs
            assert calls == ["restore"]
            stale = recovery_request(pause, request_id="recover-2")
            assert "HEAD_CONFLICT" in (await reenter(engine, stale)).reason
            monkeypatch.setattr(boundary, "restore_approval_context", restore)
            await assert_outcome_lock_boundaries(monkeypatch, journal, pause, boundaries)
            replacement = {**stale, "expected_recovery_digest": records[0].digest()}
            assert (await reenter(engine, replacement)).succeeded
            assert boundaries == ["retain_locked", "finalize_unlocked"]
            assert "SUPERSEDED" in (await reenter(engine, request)).reason
            async with journal.transaction(pause.session_id) as tx:
                records = await tx.approval_pauses.recoveries()
                assert len(records) == 2 and await tx.approval_pauses.latest() == pause
            # Publication must not claim success after referenced recovery history disappears.
            async with aiosqlite.connect(journal.db_path) as connection:
                await connection.execute("DELETE FROM epic_approval_recoveries WHERE ordinal=2")
                await connection.commit()
            missing = await reenter(engine)
            assert not missing.succeeded and "RECOVERY_EVIDENCE_CONFLICT" in missing.reason


async def assert_outcome_lock_boundaries(monkeypatch, journal, pause, observed):
    lock = EpicContinuationLocks(journal.db_path)
    reference = EpicContinuationLockRef.model_validate(pause.artifacts["epic_continuation_lock"])
    retain, finalize = EpicRunFinalizer.retain_outcome, EpicRunFinalizer.finalize_outcome

    async def retained(owner, *args, **kwargs):
        result = await retain(owner, *args, **kwargs)
        with pytest.raises(ValueError, match="owner_busy"):
            async with lock.hold(pause.session_id, expected=reference):
                pytest.fail("continuation unlocked before its retained outcome")
        observed.append("retain_locked")
        return result

    async def finalized(owner, outcome):
        async with lock.hold(pause.session_id, expected=reference), journal.transaction(pause.session_id) as tx:
            assert await tx.get_outcome() == outcome
        observed.append("finalize_unlocked")
        return await finalize(owner, outcome)

    monkeypatch.setattr(EpicRunFinalizer, "retain_outcome", retained)
    monkeypatch.setattr(EpicRunFinalizer, "finalize_outcome", finalized)
