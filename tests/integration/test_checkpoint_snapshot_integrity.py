"""Integration controls for immutable checkpoint content on resume and approval recovery.

The model and physical tool adapter are controlled. Checkpoint publication, storage,
recovery and the tool adapter's local file writes use the real local composition.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path

import pytest

from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.turn_tool_control_plane_recovery import _same_attempt_resume_decision_id
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_artifact_writer import TurnArtifactWriter
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import AttemptState, RecoveryActionClass, RunState
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from tests.helpers.turn_artifacts import artifact_destination, artifact_test_utc_now, write_checkpoint_fixture
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock
from tests.integration.test_epic_approval_continuation import approval_engine
from tests.integration.test_epic_approval_recovery import claimed_process, recovery_request, reenter
from tests.integration.test_turn_executor_control_plane import _context, _issue, _Model, _role

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class _PhysicalToolbox:
    def __init__(self, root: Path):
        self.root, self.calls = root, 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        assert tool_name == "write_file"
        target = self.root / args["path"]
        await asyncio.to_thread(target.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(target.write_text, args["content"], encoding="utf-8")
        return {"ok": True, "tool": tool_name, "touched_paths": [args["path"]], "call_count": self.calls}


def _observe_snapshot(directory, mode):
    snapshots = sorted(directory.glob("control_plane_checkpoint_snapshot_*.json"))
    assert len(snapshots) == 1
    path = snapshots[0]
    original = path.read_bytes()
    payload = json.loads(original)
    if mode == "changed-plan":
        payload["tool_calls"][0]["args"]["content"] = "substituted-checkpoint-content"
    if mode != "unchanged":
        payload = dict(reversed(list(payload.items())))
        path.write_text(json.dumps(payload, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
    current = path.read_bytes()
    assert (current == original) is (mode == "unchanged")
    return {"name": path.name, "before_sha256": hashlib.sha256(original).hexdigest(),
            "after_sha256": hashlib.sha256(current).hexdigest(), "payload": payload}


def _file_observation(path):
    if not path.is_file():
        return {"exists": path.exists(), "sha256": None, "text": None}
    content = path.read_bytes()
    return {"exists": True, "sha256": hashlib.sha256(content).hexdigest(), "text": content.decode("utf-8")}


async def _child_state(service, run_id):
    run = await service.execution_repository.get_run_record(run_id=run_id)
    attempts = await service.execution_repository.list_attempt_records(run_id=run_id)
    steps, checkpoints, acceptances = [], [], []
    for attempt in attempts:
        steps.extend(await service.execution_repository.list_step_records(attempt_id=attempt.attempt_id))
        rows = await service.publication.repository.list_checkpoints(parent_ref=attempt.attempt_id)
        checkpoints.extend(rows)
        for row in rows:
            acceptances.append(await service.publication.repository.get_checkpoint_acceptance(
                checkpoint_id=row.checkpoint_id))
    effects = await service.publication.repository.list_effect_journal_entries(run_id=run_id)
    truth = await service.publication.repository.get_final_truth(run_id=run_id)
    decision = await service.publication.repository.get_recovery_decision(
        decision_id=_same_attempt_resume_decision_id(run_id=run_id, attempt_ordinal=1),
    )
    def dump(row):
        return None if row is None else row.model_dump(mode="json")

    return {"run": dump(run), "attempts": list(map(dump, attempts)), "steps": list(map(dump, steps)),
            "effects": list(map(dump, effects)), "checkpoints": list(map(dump, checkpoints)),
            "acceptances": list(map(dump, acceptances)), "truth": dump(truth),
            "recovery_decision": dump(decision)}


async def _seed_resume(root):
    service = build_turn_tool_control_plane_service(root / "control_plane.sqlite3")
    executor = TurnExecutor(StateMachine(), ToolGate(organization=None, workspace_root=root),
        workspace=root, control_plane_service=service, utc_now=artifact_test_utc_now)
    turn = ExecutionTurn(timestamp=None, role="developer", issue_id="ISSUE-1", content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})])
    await write_checkpoint_fixture(executor=executor, turn=turn, context=_context(), prompt_hash="integrity-prompt")
    return service, executor


@pytest.mark.parametrize("mode", ["unchanged", "reformatted", "changed-plan"])
@pytest.mark.usefixtures("deterministic_turn_clock")
# Layer: integration
async def test_pre_effect_resume_binds_checkpoint_content(tmp_path, record_property, mode):
    service, executor = await _seed_resume(tmp_path)
    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    directory = tmp_path / "observability/run-1/issue-1/001_developer"
    snapshot = await asyncio.to_thread(_observe_snapshot, directory, mode)
    before = await _child_state(service, run_id)
    model, toolbox = _Model(), _PhysicalToolbox(tmp_path)
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    after = await _child_state(service, run_id)
    output = await asyncio.to_thread(_file_observation, tmp_path / "agent_output/out.txt")
    retained = await asyncio.to_thread(_file_observation, directory / snapshot["name"])
    record_property("checkpoint_resume_integrity_observation", json.dumps({
        "mode": mode, "snapshot": snapshot, "before": before, "after": after,
        "success": result.success, "error": result.error, "model_calls": model.calls,
        "tool_calls": toolbox.calls, "output": output, "snapshot_after": retained}, sort_keys=True))
    decision_id = _same_attempt_resume_decision_id(run_id=run_id, attempt_ordinal=1)
    assert before["recovery_decision"] is None and after["recovery_decision"] is not None
    assert len(before["attempts"]) == len(after["attempts"]) == 1
    assert after["attempts"][0]["attempt_id"] == before["attempts"][0]["attempt_id"]
    decision = after["recovery_decision"]
    checkpoint, acceptance = before["checkpoints"][0], before["acceptances"][0]
    assert decision["decision_id"] == decision_id
    assert decision["failed_attempt_id"] == decision["resumed_attempt_id"] == before["attempts"][0]["attempt_id"]
    assert decision["new_attempt_id"] is None
    assert decision["authorized_next_action"] == RecoveryActionClass.RESUME_FROM_CHECKPOINT.value
    assert decision["target_checkpoint_id"] == checkpoint["checkpoint_id"]
    assert decision["rationale_ref"] == acceptance["acceptance_id"]
    assert decision["required_precondition_refs"] == [
        checkpoint["checkpoint_id"], acceptance["acceptance_id"], checkpoint["state_snapshot_ref"],
    ]
    assert model.calls == 0
    assert after["checkpoints"] == before["checkpoints"] and after["acceptances"] == before["acceptances"]
    assert retained["sha256"] == snapshot["after_sha256"]
    if mode == "changed-plan":
        assert result.success is False and "E_CHECKPOINT_SNAPSHOT_INTEGRITY_MISMATCH" in result.error
        assert toolbox.calls == 0 and output["exists"] is False
        assert after["run"] == before["run"] and after["attempts"] == before["attempts"]
        assert after["run"]["lifecycle_state"] == RunState.EXECUTING.value
        assert after["attempts"][0]["attempt_state"] == AttemptState.EXECUTING.value
        assert after["steps"] == after["effects"] == [] and after["truth"] is None
    else:
        assert result.success is True and result.turn.note == "control_plane_checkpoint_resume"
        assert toolbox.calls == 1 and output["text"] == "ok"
        assert len(after["steps"]) == len(after["effects"]) == 1
        assert after["truth"]["result_class"] == "success"


@pytest.mark.parametrize("mode", ["unchanged", "reformatted", "changed-plan"])
# Layer: integration
async def test_approval_recovery_binds_checkpoint_content(tmp_path, monkeypatch, record_property, mode):
    async with claimed_process(tmp_path) as (child, pause):
        child.kill()
        await asyncio.wait_for(child.communicate(), 15)
        identity = next(iter(pause.approvals.values()))
        destination = artifact_destination(TurnArtifactWriter(tmp_path / "workspace"),
            session_id=pause.session_id, issue_id=identity["issue_id"], role_name=identity["seat_name"],
            turn_index=identity["payload_json"]["turn_index"])
        snapshot = await asyncio.to_thread(_observe_snapshot, destination.output_dir, mode)
        async with approval_engine(tmp_path, monkeypatch) as engine:
            result = await reenter(engine, recovery_request(pause))
            journal = engine._pipeline.epic_publication.repository
            async with journal.transaction(pause.session_id) as tx:
                recoveries = await tx.approval_pauses.recoveries()
                outcome, latest = await tx.get_outcome(), await tx.approval_pauses.latest()
            output = await asyncio.to_thread(_file_observation, tmp_path / "workspace/agent_output/approved.txt")
            retained = await asyncio.to_thread(_file_observation, destination.output_dir / snapshot["name"])
            record_property("checkpoint_approval_integrity_observation", json.dumps({
                "mode": mode, "snapshot": snapshot, "result": result.model_dump(mode="json"),
                "recoveries": [row.model_dump(mode="json") for row in recoveries],
                "output": output, "snapshot_after": retained, "pause_unchanged": latest == pause}, sort_keys=True))
            assert latest == pause and retained["sha256"] == snapshot["after_sha256"]
            if mode == "changed-plan":
                assert result.observation == "unresolved" and result.succeeded is False
                assert "E_CHECKPOINT_SNAPSHOT_INTEGRITY_MISMATCH" in result.reason
                assert recoveries == [] and outcome is None and output["exists"] is False
            else:
                assert result.observation == "published" and result.succeeded is True
                assert len(recoveries) == 1 and outcome is not None
                assert output["text"] == "approved"
