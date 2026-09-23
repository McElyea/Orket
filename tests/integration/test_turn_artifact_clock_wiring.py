"""Layer: integration. A pipeline-selected clock reaches turn artifacts and approvals."""
from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.workflows import orchestrator_ops
from orket.application.workflows.turn_artifact_destination import TurnArtifactDestination
from orket.application.workflows.turn_executor import TurnExecutor
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _RecordingInputs(RuntimeInputService):
    def __init__(self) -> None:
        self.current = datetime(2044, 6, 1, 12, tzinfo=UTC)
        self.observations: list[datetime] = []

    def utc_now(self) -> datetime:
        value = self.current
        self.current += timedelta(seconds=1)
        self.observations.append(value)
        return value


class _ControlledModel:
    def __init__(self, required_write_paths: tuple[str, ...]) -> None:
        self.required_write_paths = required_write_paths

    async def complete(self, messages):  # type: ignore[no-untyped-def]
        assert messages
        return {
            "content": json.dumps({
                "content": "",
                "tool_calls": [
                    {"tool": "write_file", "args": {"path": path, "content": "ok"}}
                    for path in self.required_write_paths
                ],
            }),
            "raw": {"total_tokens": 1},
        }


class _ControlledToolbox:
    def __init__(self) -> None:
        self.paths: list[str] = []
        self.statuses: list[str] = []

    async def execute(self, tool_name, args, context=None):  # type: ignore[no-untyped-def]
        assert context["session_id"] == "clock-session"
        if tool_name == "update_issue_status":
            self.statuses.append(str(args["status"]))
            return {"ok": True, "tool": tool_name, "status": args["status"]}
        assert tool_name == "write_file"
        self.paths.append(str(args["path"]))
        return {"ok": True, "tool": tool_name, "touched_paths": [args["path"]]}


async def _prepare_empty_epic(root: Path) -> None:
    await asyncio.to_thread(_write_epic_assets, root, "clock_wiring_epic")
    team_path = root / "model/core/teams/standard.json"
    team = json.loads(await asyncio.to_thread(team_path.read_text, encoding="utf-8"))
    team["seats"]["code_reviewer"] = {"name": "Reviewer", "roles": ["code_reviewer"]}
    await asyncio.to_thread(team_path.write_text, json.dumps(team), encoding="utf-8")


async def _capture_production_executor(pipeline, monkeypatch) -> TurnExecutor:
    constructed: list[tuple[TurnExecutor, object]] = []
    actual_type = TurnExecutor

    def recording_constructor(*args, **kwargs):  # type: ignore[no-untyped-def]
        executor = actual_type(*args, **kwargs)
        constructed.append((executor, kwargs["utc_now"]))
        return executor

    monkeypatch.setattr(orchestrator_ops, "TurnExecutor", recording_constructor)
    execute_epic = pipeline.orchestrator.execute_epic

    async def empty_epic(**kwargs):  # type: ignore[no-untyped-def]
        await pipeline.async_cards.update_status("ISSUE-1", CardStatus.CANCELED)
        return await execute_epic(**kwargs)

    monkeypatch.setattr(pipeline.orchestrator, "execute_epic", empty_epic)
    await pipeline.run_epic("clock_wiring_epic", build_id="clock-build", session_id="clock-bootstrap")
    assert len(constructed) == 1
    executor, callback = constructed[0]
    assert callback is pipeline.orchestrator.turn_clock
    assert executor.utc_now is callback and executor.response_parser.utc_now is callback
    return executor


async def _turn_context(orchestrator, issue: IssueConfig) -> dict:
    context = await orchestrator._build_turn_context(
        run_id="clock-session", issue=issue, seat_name="developer", roles_to_load=["coder"],
        turn_status=CardStatus.IN_PROGRESS, selected_model="controlled", resume_mode=False,
    )
    context.update(protocol_governed_enabled=False, compact_turn_packet_enabled=False,
                   approval_required_tools=[], stage_gate_mode="auto")
    return context


async def _assert_approval_clock(pipeline, executor, context, clock) -> None:
    destination = TurnArtifactDestination(
        writer=executor.artifact_writer, workspace=pipeline.workspace,
        session_id="clock-session", issue_id="CLOCK-ISSUE", role_name="developer",
        role_id="CLOCK-ROLE", turn_index=2,
    )
    callback = context["create_pending_gate_request"]
    request_id = await callback(destination=destination, tool_name="write_file",
                                tool_args={"path": "agent_output/approved.txt", "content": "ok"})
    rows = await pipeline.orchestrator.pending_gates.list_requests(
        session_id="clock-session", status="pending")
    assert len(rows) == 1 and rows[0]["request_id"] == request_id
    assert rows[0]["created_at"] == clock.observations[-1].isoformat()
    reservation = await pipeline.orchestrator.control_plane_publication.repository.get_latest_reservation_record(
        reservation_id=f"approval-reservation:{request_id}")
    assert reservation is not None
    assert reservation.creation_timestamp == rows[0]["created_at"]
    assert reservation.holder_ref == destination.control_plane_run_id


async def test_pipeline_selected_clock_reaches_real_parser_and_context_approval(
    test_root, workspace, db_path, monkeypatch,
) -> None:
    """Controlled model composition; no actual provider or full successful epic claim."""
    await _prepare_empty_epic(test_root)
    clock = _RecordingInputs()
    async with ExecutionPipeline.open(
        workspace=workspace, config_root=test_root, db_path=db_path, runtime_inputs=clock,
    ) as pipeline:
        executor = await _capture_production_executor(pipeline, monkeypatch)
        assert getattr(pipeline.orchestrator.turn_clock, "__self__", None) is clock
        issue = IssueConfig(id="CLOCK-ISSUE", summary="Observe the selected clock",
                            seat="developer", status=CardStatus.IN_PROGRESS)
        role = RoleConfig(id="CLOCK-ROLE", summary="developer", description="Build code",
                          tools=["write_file"])
        context = await _turn_context(pipeline.orchestrator, issue)
        required_write_paths = tuple(
            str(path) for path in context.get("required_write_paths", []) if str(path)
        )
        assert required_write_paths
        clock.observations.clear()
        toolbox = _ControlledToolbox()
        result = await executor.execute_turn(
            issue, role, _ControlledModel(required_write_paths), toolbox, context)
        assert result.success and result.turn is not None
        assert toolbox.paths == list(required_write_paths)
        assert toolbox.statuses == list(context["required_statuses"])
        assert len(clock.observations) == 2 and result.turn.timestamp == clock.observations[0]
        turn_dir = workspace / "observability/clock-session/clock-issue/001_developer"
        artifacts = ("model_response.txt", "model_response_raw.json", "tool_parser_diagnostics.json")
        assert all(await asyncio.gather(*(asyncio.to_thread((turn_dir / name).is_file) for name in artifacts)))
        checkpoint = json.loads(await asyncio.to_thread(
            (turn_dir / "checkpoint.json").read_text, encoding="utf-8"))
        assert checkpoint["captured_at"] == clock.observations[1].isoformat()
        await _assert_approval_clock(pipeline, executor, context, clock)
        assert len(clock.observations) == 3
