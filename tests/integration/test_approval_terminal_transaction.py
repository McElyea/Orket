"""Denial retains operator intent without committing a partial child closeout."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import aiosqlite
import httpx
import pytest
from fastapi import FastAPI

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.services import governed_turn_tool_approval_continuation_service as continuation
from orket.application.services import turn_tool_control_plane_closeout as closeout
from orket.application.services import turn_tool_control_plane_service as turn_service
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.interfaces.routers.approvals import build_approvals_router
from tests.helpers.gitea_control_plane_clock import ordered_utc_clock
from tests.integration.test_epic_approval_continuation import approval_engine, pause
from tests.integration.test_governed_agent_terminal_history import damage_terminal_history, logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
FAULT = "approval-terminal-write-interrupted"
WRITES = [
    (AsyncControlPlaneRecordRepository, "save_recovery_decision"),
    (AsyncControlPlaneExecutionRepository, "save_attempt_record"),
    (AsyncControlPlaneRecordRepository, "save_final_truth"),
    (AsyncControlPlaneExecutionRepository, "save_run_record"),
    (ControlPlanePublicationService, "publish_lease"),
    (ControlPlanePublicationService, "publish_resource"),
]


@pytest.fixture(autouse=True)
def approval_clock(monkeypatch):
    """Reach the selected write deterministically; clock refusal has its own control."""
    clock = ordered_utc_clock()
    monkeypatch.setattr(turn_service, "utc_now", clock)
    monkeypatch.setattr(closeout, "utc_now", clock)


async def decide(engine, approval):
    app = FastAPI()
    app.include_router(build_approvals_router(lambda: engine), prefix="/v1")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        return await client.post(f"/v1/approvals/{approval['approval_id']}/decision", json={"decision": "deny"})


def capture_closeout(monkeypatch, db):
    state = {}
    original = continuation.stop_approval_execution

    async def observed(**kwargs):
        state["before"] = await logical_state(db)
        return await original(**kwargs)

    monkeypatch.setattr(continuation, "stop_approval_execution", observed)
    return state


@pytest.mark.parametrize("owner,method", WRITES, ids=[method for _, method in WRITES])
@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError], ids=["error", "cancel"])
# Layer: integration
async def test_approval_denial_rolls_back_every_terminal_write(tmp_path, monkeypatch, owner, method, error):
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        approval = await pause(engine)
        db = engine.control_plane_execution_repository.db_path
        with monkeypatch.context() as patch:
            state = capture_closeout(patch, db)
            original = getattr(owner, method)

            async def interrupted(*args, **kwargs):
                result = await original(*args, **kwargs)
                if "before" in state:
                    state["interrupted"] = True
                    raise error(FAULT)
                return result

            patch.setattr(owner, method, interrupted)
            if error is asyncio.CancelledError:
                with pytest.raises(asyncio.CancelledError, match=FAULT):
                    await decide(engine, approval)
            else:
                response = await decide(engine, approval)
                assert response.status_code == 409 and FAULT in response.text
            assert state["interrupted"]
            assert await logical_state(db) == state["before"]
        retained = await engine.get_approval(approval["approval_id"])
        assert retained["status"] == "DENIED"
        retry = await decide(engine, approval)
        assert retry.status_code == 200, retry.text
        assert retry.json()["runtime_result"]["observation"] == "published"
        assert not (tmp_path / "workspace/agent_output/approved.txt").exists()


# Layer: integration
async def test_approval_denial_clock_reversal_preserves_unfinished_authority(tmp_path, monkeypatch):
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        approval = await pause(engine)
        db = engine.control_plane_execution_repository.db_path
        with monkeypatch.context() as patch:
            state = capture_closeout(patch, db)
            patch.setattr(closeout, "utc_now", lambda: "1980-01-01T00:00:00+00:00")

            async def unreachable_resource(*args, **kwargs):
                raise AssertionError("reversed lease time must refuse before resource publication")

            patch.setattr(ControlPlanePublicationService, "publish_resource", unreachable_resource)
            response = await decide(engine, approval)
            assert response.status_code == 422, response.text
            assert "lease publication timestamps must increase monotonically" in response.text
            assert await logical_state(db) == state["before"]
        retry = await decide(engine, approval)
        assert retry.status_code == 200, retry.text
        assert retry.json()["runtime_result"]["succeeded"] is False


@pytest.mark.parametrize("damage", ["unreferenced-truth", "unfinished-attempt", "missing-truth", "active-lease"])
# Layer: integration
async def test_approval_reentry_refuses_partial_terminal_authority(tmp_path, monkeypatch, damage):
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        approval = await pause(engine)

        async def stop_before_parent(*args, **kwargs):
            raise asyncio.CancelledError("retained-child-closeout")

        with monkeypatch.context() as patch:
            patch.setattr(continuation.GovernedTurnToolApprovalContinuationService, "_resume_epic", stop_before_parent)
            with pytest.raises(asyncio.CancelledError, match="retained-child-closeout"):
                await decide(engine, approval)
        db = engine.control_plane_execution_repository.db_path
        run = await engine.control_plane_execution_repository.get_run_record(run_id=approval["control_plane_target_ref"])
        attempt = await engine.control_plane_execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
        truth = await engine.control_plane_repository.get_final_truth(run_id=run.run_id)
        if damage == "active-lease":
            async with aiosqlite.connect(db) as connection:
                await connection.execute("DELETE FROM lease_records WHERE payload_json LIKE '%lease_released%'")
                await connection.commit()
        else:
            await damage_terminal_history(db, SimpleNamespace(run=run, attempt=attempt, final_truth=truth), damage)
        before = await logical_state(db)
        response = await decide(engine, approval)
        assert response.status_code in {409, 422}, response.text
        assert await logical_state(db) == before
        assert not (tmp_path / "workspace/agent_output/approved.txt").exists()
