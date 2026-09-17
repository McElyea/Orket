"""Stale persisted observations cannot reverse real composed family closeout."""
import asyncio

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
    ControlPlaneExecutionConflictError,
)
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.state_machine import StateMachine
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.helpers.outward_authorization import boundary as boundary
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_family_terminal_authority import agent_flow, card_flow, outward_flow, retained_results
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role, _Toolbox

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("elapsed_agent_clock")]


@pytest.mark.parametrize("family", ["outward", "cards", "governed_agent"])
@pytest.mark.parametrize("kind", ["run", "attempt"])
# Layer: integration
async def test_family_closeout_refuses_earlier_admission_state(
    family, kind, tmp_path, test_root, workspace, db_path, boundary, monkeypatch,
):
    original_save = getattr(AsyncControlPlaneExecutionRepository, f"save_{kind}_record")
    observed = {}

    async def capture(repository, *, record):
        saved = await original_save(repository, record=record)
        observed.setdefault(getattr(saved, f"{kind}_id"), saved.model_copy(deep=True))
        return saved

    monkeypatch.setattr(AsyncControlPlaneExecutionRepository, f"save_{kind}_record", capture)
    if family == "outward":
        db, _ = await outward_flow(tmp_path, boundary)
    elif family == "cards":
        db, _ = await card_flow(test_root, workspace, db_path, monkeypatch)
    else:
        db, _ = await agent_flow(tmp_path)
    before = await retained_results(db)
    assert len(before) == 1 and before[0]["truth"]["result_class"] == "success"
    identity = before[0]["run"]["run_id" if kind == "run" else "current_attempt_id"]
    stale = observed[identity]
    independent = AsyncControlPlaneExecutionRepository(db)
    current = await getattr(independent, f"get_{kind}_record")(**{f"{kind}_id": identity})
    assert stale.state_revision == 0 and current.state_revision > stale.state_revision
    with pytest.raises(ControlPlaneExecutionConflictError, match="STATE_CONFLICT"):
        await getattr(independent, f"save_{kind}_record")(record=stale)
    assert await getattr(independent, f"get_{kind}_record")(**{f"{kind}_id": identity}) == current
    assert await retained_results(db) == before


class ObservingPhysicalToolbox(_Toolbox):
    def __init__(self, workspace, repository):
        super().__init__()
        self.workspace, self.repository, self.observed = workspace, repository, {}

    async def execute(self, tool_name, args, context=None):
        run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
        run = await self.repository.get_run_record(run_id=run_id)
        attempt = await self.repository.get_attempt_record(attempt_id=run.current_attempt_id)
        steps = await self.repository.list_step_records(attempt_id=attempt.attempt_id)
        assert len(steps) == 1 and steps[0].closure_classification == "dispatch_started"
        self.observed = {"run": run, "attempt": attempt, "step": steps[0]}
        target = self.workspace / "agent_output/out.txt"
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_text, "ok", encoding="utf-8")
        return await super().execute(tool_name, args, context)


# Layer: integration
async def test_physical_turn_closeout_refuses_original_dispatch_state(tmp_path, deterministic_turn_clock):
    path = tmp_path / "control_plane.sqlite3"
    control = build_turn_tool_control_plane_service(path)
    observer = AsyncControlPlaneExecutionRepository(path)
    toolbox, model = ObservingPhysicalToolbox(tmp_path, observer), _Model()
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=tmp_path),
                            workspace=tmp_path, control_plane_service=control)
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    assert result.success and toolbox.calls == model.calls == 1
    assert await asyncio.to_thread((tmp_path / "agent_output/out.txt").read_text, encoding="utf-8") == "ok"
    for kind, stale in toolbox.observed.items():
        identity = getattr(stale, f"{kind}_id")
        current = await getattr(observer, f"get_{kind}_record")(**{f"{kind}_id": identity})
        assert current.state_revision > stale.state_revision
        with pytest.raises(ControlPlaneExecutionConflictError, match="STATE_CONFLICT"):
            await getattr(observer, f"save_{kind}_record")(record=stale)
        assert await getattr(observer, f"get_{kind}_record")(**{f"{kind}_id": identity}) == current
    assert toolbox.calls == model.calls == 1
    truth = await control.publication.repository.get_final_truth(run_id=toolbox.observed["run"].run_id)
    assert truth.result_class.value == "success"
