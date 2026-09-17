"""The retained epic-pause consumer shares denial's child transaction boundary."""
from __future__ import annotations

import asyncio

import pytest

from orket.application.services import epic_approval_pause_service as pauses
from orket.application.services import governed_turn_tool_approval_continuation_service as continuation
from orket.application.services.runtime_execution_result_service import RuntimeExecutionCancelled
from tests.integration.test_approval_terminal_transaction import FAULT, WRITES, decide
from tests.integration.test_approval_terminal_transaction import approval_clock as approval_clock
from tests.integration.test_epic_approval_continuation import approval_engine, pause
from tests.integration.test_governed_agent_terminal_history import logical_state

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("owner,method", WRITES, ids=[method for _, method in WRITES])
@pytest.mark.parametrize("error", [RuntimeError, asyncio.CancelledError], ids=["error", "cancel"])
# Layer: integration
async def test_restarted_epic_denial_rolls_back_child_closeout(tmp_path, monkeypatch, owner, method, error):
    async with approval_engine(tmp_path, monkeypatch, setup=True) as engine:
        approval = await pause(engine)

        async def stop_before_child(**kwargs):
            raise RuntimeError("interrupted-after-decision")

        with monkeypatch.context() as patch:
            patch.setattr(continuation, "stop_approval_execution", stop_before_child)
            response = await decide(engine, approval)
            assert response.status_code == 409 and "interrupted-after-decision" in response.text
    async with approval_engine(tmp_path, monkeypatch) as engine:
        state = {}
        db = engine.control_plane_execution_repository.db_path
        original_stop = pauses.stop_approval_execution
        original_write = getattr(owner, method)

        async def observed(**kwargs):
            state["before"] = await logical_state(db)
            return await original_stop(**kwargs)

        async def interrupted(*args, **kwargs):
            result = await original_write(*args, **kwargs)
            if "before" in state:
                state["interrupted"] = True
                raise error(FAULT)
            return result

        with monkeypatch.context() as patch:
            patch.setattr(pauses, "stop_approval_execution", observed)
            patch.setattr(owner, method, interrupted)
            if error is asyncio.CancelledError:
                with pytest.raises(RuntimeExecutionCancelled) as cancelled:
                    await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build")
                assert FAULT in str(cancelled.value.__cause__)
                assert cancelled.value.result.observation == "cancelled"
            else:
                result = await engine.run_card("approval_required", session_id="approval-session", build_id="approval-build")
                assert result.observation == "unresolved" and FAULT in result.reason
        assert state["interrupted"]
        assert await logical_state(db) == state["before"]
        assert (await engine.get_approval(approval["approval_id"]))["status"] == "DENIED"
        assert not (tmp_path / "workspace/agent_output/approved.txt").exists()
