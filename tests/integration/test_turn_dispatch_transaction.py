"""Real SQLite dispatch admission and result publication preserve uncertain effects."""
from __future__ import annotations

import asyncio

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.turn_tool_control_plane_service import TurnToolControlPlaneError
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_governed_agent_terminal_history import logical_state
from tests.integration.test_turn_execution_ownership import executor
from tests.integration.test_turn_recovery_transaction import INPUTS, interrupt_write

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("deterministic_turn_clock")]


async def admitted(tmp_path):
    service = executor(tmp_path, tmp_path / "control_plane.sqlite3").tool_dispatcher.control_plane_service
    run, attempt = await service.begin_execution(**INPUTS, resume_mode=False)
    call = dict(run_id=run.run_id, attempt_id=attempt.attempt_id, step_id="operation-1",
                operation_id="operation-1", tool_name="write_file", binding=None,
                tool_args={"path": "agent_output/out.txt", "content": "observed"})
    return service, call


@pytest.mark.parametrize("cancellation", [False, True], ids=["exception", "cancel"])
# Layer: integration
async def test_dispatch_admission_interruption_rolls_back_marker(tmp_path, monkeypatch, cancellation):
    service, call = await admitted(tmp_path)
    before = await logical_state(service.execution_repository.db_path)
    interrupt_write(monkeypatch, "save_step_record", cancellation)
    task = asyncio.create_task(service.prepare_dispatch(**call))
    with pytest.raises(asyncio.CancelledError if cancellation else RuntimeError):
        await task
    assert await logical_state(service.execution_repository.db_path) == before
    assert not await asyncio.to_thread((tmp_path / "agent_output/out.txt").exists)


@pytest.mark.parametrize("method", ["save_step_record", "append_effect_journal_entry"])
@pytest.mark.parametrize("cancellation", [False, True], ids=["exception", "cancel"])
# Layer: integration
async def test_result_publication_interruption_preserves_uncertainty_atomically(tmp_path, monkeypatch, method, cancellation):
    service, call = await admitted(tmp_path)
    await service.prepare_dispatch(**call)
    files = AsyncFileTools(tmp_path)
    await files.write_file(call["tool_args"]["path"], call["tool_args"]["content"])
    before = await logical_state(service.execution_repository.db_path)
    interrupt_write(monkeypatch, method, cancellation)
    task = asyncio.create_task(service.publish_step_result(**call, result={"ok": True}, replayed=False))
    with pytest.raises(asyncio.CancelledError if cancellation else RuntimeError):
        await task
    assert await logical_state(service.execution_repository.db_path) == before
    assert await files.read_file(call["tool_args"]["path"]) == "observed"


@pytest.mark.parametrize("field,value", [("attempt_id", "foreign-attempt"), ("tool_name", "read_file"),
                                       ("tool_args", {"path": "another.txt"}), ("operation_id", "other-operation")])
# Layer: integration
async def test_observation_cannot_promote_another_dispatch_input(tmp_path, field, value):
    service, call = await admitted(tmp_path)
    await service.prepare_dispatch(**call)
    before = await logical_state(service.execution_repository.db_path)
    with pytest.raises(TurnToolControlPlaneError, match="authority mismatch"):
        await service.publish_step_result(**(call | {field: value}), result={"ok": True}, replayed=False)
    assert await logical_state(service.execution_repository.db_path) == before


# Layer: integration
async def test_observation_resolves_marker_without_granting_another_dispatch(tmp_path):
    service, call = await admitted(tmp_path)
    await service.prepare_dispatch(**call)
    with pytest.raises(TurnToolControlPlaneError, match="dispatch outcome unknown"):
        await service.prepare_dispatch(**call)
    await AsyncFileTools(tmp_path).write_file(call["tool_args"]["path"], "observed")
    step, effect = await service.publish_step_result(**call, result={"ok": True}, replayed=False)
    assert step.closure_classification == "step_completed" and effect.step_id == step.step_id
    with pytest.raises(TurnToolControlPlaneError, match="already admitted"):
        await service.prepare_dispatch(**call)


@pytest.mark.parametrize("action", ["terminal", "resume", "preflight"])
# Layer: integration
async def test_unknown_dispatch_cannot_release_authority_via_closeout_or_resume(tmp_path, action):
    service, call = await admitted(tmp_path)
    await service.prepare_dispatch(**call)
    before = await logical_state(service.execution_repository.db_path)
    with pytest.raises(ValueError, match="dispatch outcome unknown"):
        if action == "resume":
            await service.begin_execution(**INPUTS, resume_mode=True)
        elif action == "preflight":
            await service.publish_preflight_failure(**INPUTS, violation_reasons=["invalid"])
        else:
            await service.finalize_execution(run_id=call["run_id"], attempt_id=call["attempt_id"],
                authoritative_result_ref="no-result", violation_reasons=["interrupted"], executed_step_count=0)
    assert await logical_state(service.execution_repository.db_path) == before
