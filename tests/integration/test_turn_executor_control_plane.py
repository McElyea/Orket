# Layer: integration

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.services.control_plane_workload_catalog import TURN_TOOL_WORKLOAD
from orket.application.services.turn_tool_control_plane_recovery import recover_pre_effect_attempt_for_resume_mode
from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    namespace_resource_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.contracts import StepRecord
from orket.core.domain import (
    CapabilityClass,
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    DivergenceClass,
    LeaseStatus,
    RecoveryActionClass,
    ReservationStatus,
    ResultClass,
    RunState,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.domain.execution import ExecutionTurn, ToolCall
from orket.schema import CardStatus, IssueConfig, RoleConfig


pytestmark = pytest.mark.integration


class _Model:
    def __init__(self) -> None:
        self.calls = 0

    async def complete(self, _messages):
        self.calls += 1
        return {
            "content": (
                '{"content":"","tool_calls":[{"tool":"write_file","args":{"path":"agent_output/out.txt","content":"ok"}}]}'
            ),
            "raw": {"total_tokens": 1},
        }


class _Toolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        return {
            "ok": True,
            "tool": tool_name,
            "touched_paths": [args["path"]],
            "call_count": self.calls,
        }


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer", status=CardStatus.IN_PROGRESS)


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


def _context(*, protocol_governed_enabled: bool = True, resume_mode: bool = False) -> dict[str, object]:
    context: dict[str, object] = {
        "session_id": "run-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
        "resume_mode": resume_mode,
    }
    if protocol_governed_enabled:
        context["protocol_governed_enabled"] = True
    return context


@pytest.mark.asyncio
async def test_turn_executor_publishes_control_plane_run_attempt_step_effect_and_final_truth(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    toolbox = _Toolbox()

    result = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context())

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    attempt_id = f"{run_id}:attempt:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=attempt_id)
    steps = await control_plane.execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await control_plane.publication.repository.list_effect_journal_entries(run_id=run_id)
    checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{attempt_id}"
    )
    checkpoint_acceptance = None if checkpoint is None else await control_plane.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)
    reservations = await control_plane.publication.repository.list_reservation_records(
        reservation_id=reservation_id_for_run(run_id=run_id)
    )
    leases = await control_plane.publication.repository.list_lease_records(lease_id=lease_id_for_run(run_id=run_id))
    resources = [] if run is None else await control_plane.publication.repository.list_resource_records(
        resource_id=namespace_resource_id_for_run(run=run)
    )
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_files = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))
    receipt_rows = [
        json.loads(line)
        for line in (turn_dir / "protocol_receipts.log").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert result.success is True
    assert toolbox.calls == 1
    assert run is not None
    assert attempt is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    snapshot_payload = json.loads(snapshot_files[0].read_text(encoding="utf-8"))
    assert run.lifecycle_state.value == "completed"
    assert run.namespace_scope == "issue:ISSUE-1"
    assert attempt.attempt_state.value == "attempt_completed"
    assert len(steps) == 1
    assert steps[0].step_id
    assert steps[0].namespace_scope == "issue:ISSUE-1"
    assert steps[0].input_ref.startswith("turn-tool-call:")
    assert steps[0].output_ref.startswith("turn-tool-result:")
    assert steps[0].observed_result_classification == "tool_succeeded"
    assert "namespace:issue:ISSUE-1" in steps[0].resources_touched
    assert len(effects) == 1
    assert effects[0].step_id == steps[0].step_id
    assert effects[0].observed_result_ref == steps[0].output_ref
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
    assert checkpoint_acceptance.dependent_reservation_refs == [reservation_id_for_run(run_id=run_id)]
    assert checkpoint_acceptance.dependent_lease_refs == [lease_id_for_run(run_id=run_id)]
    assert checkpoint.state_snapshot_ref.startswith("turn-tool-checkpoint-snapshot:")
    assert len(snapshot_files) == 1
    assert snapshot_payload["namespace_scope"] == "issue:ISSUE-1"
    assert (
        snapshot_payload["control_plane"]["resumability_class"]
        == CheckpointResumabilityClass.RESUME_SAME_ATTEMPT.value
    )
    assert truth.result_class.value == "success"
    assert [record.status for record in reservations] == [ReservationStatus.ACTIVE, ReservationStatus.PROMOTED_TO_LEASE]
    assert reservations[-1].target_scope_ref == "namespace:issue:ISSUE-1"
    assert [record.status for record in leases] == [LeaseStatus.ACTIVE, LeaseStatus.RELEASED]
    assert leases[-1].resource_id == "namespace:issue:ISSUE-1"
    assert len(receipt_rows) == 1
    manifest = receipt_rows[0]["tool_invocation_manifest"]
    assert manifest["control_plane_run_id"] == run_id
    assert manifest["control_plane_attempt_id"] == attempt_id
    assert manifest["control_plane_step_id"] == steps[0].step_id
    assert manifest["control_plane_reservation_id"] == reservation_id_for_run(run_id=run_id)
    assert manifest["control_plane_lease_id"] == lease_id_for_run(run_id=run_id)
    assert manifest["control_plane_resource_id"] == "namespace:issue:ISSUE-1"
    assert [record.current_observed_state.split(";")[0] for record in resources] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]


@pytest.mark.asyncio
async def test_turn_executor_publishes_control_plane_for_non_protocol_tool_execution(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )

    await executor.execute_turn(_issue(), _role(), _Model(), _Toolbox(), _context(protocol_governed_enabled=False))

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    attempt_id = f"{run_id}:attempt:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=attempt_id)
    steps = await control_plane.execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await control_plane.publication.repository.list_effect_journal_entries(run_id=run_id)
    checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{attempt_id}"
    )
    checkpoint_acceptance = None if checkpoint is None else await control_plane.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoint.checkpoint_id
    )
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)
    reservations = await control_plane.publication.repository.list_reservation_records(
        reservation_id=reservation_id_for_run(run_id=run_id)
    )
    leases = await control_plane.publication.repository.list_lease_records(lease_id=lease_id_for_run(run_id=run_id))
    resources = [] if run is None else await control_plane.publication.repository.list_resource_records(
        resource_id=namespace_resource_id_for_run(run=run)
    )
    operation_record = executor.artifact_writer.load_operation_result(
        session_id="run-1",
        issue_id="ISSUE-1",
        role_name="developer",
        turn_index=1,
        operation_id=steps[0].step_id if steps else "missing",
    )

    assert run is not None
    assert attempt is not None
    assert checkpoint is not None
    assert checkpoint_acceptance is not None
    assert truth is not None
    assert operation_record is not None
    assert run.workload_id == TURN_TOOL_WORKLOAD.workload_id
    assert run.workload_version == TURN_TOOL_WORKLOAD.workload_version
    assert run.lifecycle_state.value == "completed"
    assert run.namespace_scope == "issue:ISSUE-1"
    assert attempt.attempt_state.value == "attempt_completed"
    assert len(steps) == 1
    assert steps[0].namespace_scope == "issue:ISSUE-1"
    assert steps[0].input_ref.startswith("turn-tool-call:")
    assert steps[0].output_ref.startswith("turn-tool-result:")
    assert "namespace:issue:ISSUE-1" in steps[0].resources_touched
    assert len(effects) == 1
    assert effects[0].authorization_basis_ref.startswith("turn-tool-authorization:")
    assert effects[0].observed_result_ref == steps[0].output_ref
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert truth.result_class.value == "success"
    assert [record.status for record in reservations] == [ReservationStatus.ACTIVE, ReservationStatus.PROMOTED_TO_LEASE]
    assert [record.status for record in leases] == [LeaseStatus.ACTIVE, LeaseStatus.RELEASED]
    assert [record.current_observed_state.split(";")[0] for record in resources] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_reuses_control_plane_checkpoint_and_effect_truth(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_files_before = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))
    snapshot_payload = json.loads(snapshot_files_before[0].read_text(encoding="utf-8"))
    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    snapshot_files_after = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    attempt_id = f"{run_id}:attempt:0001"
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    steps = await control_plane.execution_repository.list_step_records(attempt_id=attempt_id)
    effects = await control_plane.publication.repository.list_effect_journal_entries(run_id=run_id)
    checkpoints = await control_plane.publication.repository.list_checkpoints(parent_ref=attempt_id)
    checkpoint_acceptance = None if not checkpoints else await control_plane.publication.repository.get_checkpoint_acceptance(
        checkpoint_id=checkpoints[-1].checkpoint_id
    )

    assert first.success is True
    assert second.success is True
    assert model.calls == 1
    assert toolbox.calls == 1
    assert second.turn is not None
    assert second.turn.note == "control_plane_completed_replay"
    assert second.turn.raw["prompt_hash"] == snapshot_payload["prompt_hash"]
    assert second.turn.raw["model"] == snapshot_payload["model"]
    assert second.turn.raw["control_plane_replay"]["checkpoint_id"] == checkpoints[0].checkpoint_id
    assert snapshot_files_after == snapshot_files_before
    assert len(attempts) == 1
    assert len(steps) == 1
    assert len(effects) == 1
    assert len(checkpoints) == 1
    assert checkpoint_acceptance is not None
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT


@pytest.mark.asyncio
async def test_turn_executor_completed_governed_reentry_reuses_artifacts_before_model_without_resume_mode(
    tmp_path: Path,
) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_files_before = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))
    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=False))
    snapshot_files_after = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    effects = await control_plane.publication.repository.list_effect_journal_entries(run_id=run_id)

    assert first.success is True
    assert second.success is True
    assert model.calls == 1
    assert toolbox.calls == 1
    assert second.turn is not None
    assert second.turn.note == "control_plane_completed_replay"
    assert second.turn.tool_calls[0].result is not None
    assert second.turn.tool_calls[0].result.get("call_count") == 1
    assert second.turn.raw["control_plane_replay"]["artifact_reused"] is True
    assert snapshot_files_after == snapshot_files_before
    assert len(attempts) == 1
    assert len(effects) == 1


@pytest.mark.asyncio
async def test_turn_executor_completed_governed_reentry_requires_snapshot_artifact(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_path = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))[0]
    snapshot_path.unlink()

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))

    assert first.success is True
    assert second.success is False
    assert second.error is not None
    assert "missing immutable checkpoint snapshot artifact" in second.error
    assert model.calls == 1
    assert toolbox.calls == 1


@pytest.mark.asyncio
async def test_turn_executor_completed_governed_reentry_requires_checkpoint_plan_alignment(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_path = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))[0]
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_payload["tool_calls"][0]["args"] = {"path": "agent_output/other.txt", "content": "wrong"}
    snapshot_path.write_text(json.dumps(snapshot_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=False))

    assert first.success is True
    assert second.success is False
    assert second.error is not None
    assert "arguments do not match checkpoint tool plan" in second.error
    assert model.calls == 1
    assert toolbox.calls == 1


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_recovers_pre_effect_unfinished_attempt_via_same_attempt_checkpoint(
    tmp_path: Path,
) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    tool_args = {"path": "agent_output/out.txt", "content": "ok"}
    pre_effect_turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args=tool_args)],
    )

    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=pre_effect_turn,
        context=_context(),
        prompt_hash="prompt-hash-1",
    )

    model = _Model()
    toolbox = _Toolbox()
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    first_snapshot_path = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))[0]
    first_snapshot_payload = json.loads(first_snapshot_path.read_text(encoding="utf-8"))
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    snapshot_files_after = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    first_checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run_id}:attempt:0001"
    )
    second_checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run_id}:attempt:0002"
    )
    decision = await control_plane.publication.repository.get_recovery_decision(
        decision_id=f"turn-tool-recovery:{run_id}:same-attempt:0001"
    )

    assert result.success is True
    assert model.calls == 0
    assert toolbox.calls == 1
    assert result.turn is not None
    assert result.turn.note == "control_plane_checkpoint_resume"
    assert run is not None
    assert len(attempts) == 1
    assert attempts[0].attempt_state.value == "attempt_completed"
    assert first_checkpoint is not None
    assert first_checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_SAME_ATTEMPT
    assert second_checkpoint is None
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.RESUME_FROM_CHECKPOINT
    assert decision.failed_attempt_id == attempts[0].attempt_id
    assert decision.resumed_attempt_id == attempts[0].attempt_id
    assert decision.new_attempt_id is None
    assert decision.target_checkpoint_id == first_checkpoint.checkpoint_id
    assert first_checkpoint.state_snapshot_ref in decision.required_precondition_refs
    assert snapshot_files_after == [first_snapshot_path]
    assert result.turn.raw["prompt_hash"] == first_snapshot_payload["prompt_hash"]
    assert result.turn.raw["model"] == first_snapshot_payload["model"]
    assert result.turn.raw["prompt_metadata"] == first_snapshot_payload["prompt_metadata"]
    assert result.turn.raw["state_delta"] == first_snapshot_payload["state_delta"]
    assert (
        result.turn.raw["control_plane_resume"]["resumability_class"]
        == CheckpointResumabilityClass.RESUME_SAME_ATTEMPT.value
    )


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_rejects_post_effect_unfinished_attempt(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    tool_args = {"path": "agent_output/out.txt", "content": "ok"}
    pre_effect_turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args=tool_args)],
    )

    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=pre_effect_turn,
        context=_context(),
        prompt_hash="prompt-hash-2",
    )

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    attempt_id = f"{run_id}:attempt:0001"
    await control_plane.publish_step_result(
        run_id=run_id,
        attempt_id=attempt_id,
        step_id="op-1",
        tool_name="write_file",
        tool_args=tool_args,
        result={"ok": True, "touched_paths": [tool_args["path"]]},
        binding=None,
        operation_id="op-1",
        replayed=False,
    )

    toolbox = _Toolbox()
    result = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context(resume_mode=True))
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)
    decision = (
        None
        if not attempts or attempts[0].recovery_decision_id is None
        else await control_plane.publication.repository.get_recovery_decision(
            decision_id=attempts[0].recovery_decision_id
        )
    )
    reconciliation = (
        None
        if decision is None
        else await control_plane.publication.repository.get_reconciliation_record(
            reconciliation_id=decision.rationale_ref
        )
    )

    assert result.success is False
    assert toolbox.calls == 0
    assert result.error is not None
    assert "run was closed from reconciliation evidence" in result.error
    assert run is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert len(attempts) == 1
    assert attempts[0].attempt_state.value == "attempt_interrupted"
    assert attempts[0].side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert reconciliation is not None
    assert decision.rationale_ref == reconciliation.reconciliation_id
    assert reconciliation.reconciliation_id in decision.required_precondition_refs
    assert reconciliation.divergence_class is DivergenceClass.UNEXPECTED_EFFECT_OBSERVED
    assert reconciliation.safe_continuation_class is SafeContinuationClass.UNSAFE_TO_CONTINUE
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert truth.authoritative_result_ref == reconciliation.reconciliation_id


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_rejects_post_effect_truth_on_resumed_attempt_before_model(
    tmp_path: Path,
) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    tool_args = {"path": "agent_output/out.txt", "content": "ok"}
    pre_effect_turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args=tool_args)],
    )

    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=pre_effect_turn,
        context=_context(),
        prompt_hash="prompt-hash-3",
    )

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    initial_run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    initial_attempt = await control_plane.execution_repository.get_attempt_record(
        attempt_id=f"{run_id}:attempt:0001"
    )
    assert initial_run is not None
    assert initial_attempt is not None
    _, resumed_attempt = await recover_pre_effect_attempt_for_resume_mode(
        execution_repository=control_plane.execution_repository,
        publication=control_plane.publication,
        run=initial_run,
        current_attempt=initial_attempt,
    )
    assert resumed_attempt.attempt_id == initial_attempt.attempt_id
    await control_plane.publish_step_result(
        run_id=run_id,
        attempt_id=resumed_attempt.attempt_id,
        step_id="op-resumed-post-effect",
        tool_name="write_file",
        tool_args=tool_args,
        result={"ok": True, "touched_paths": [tool_args["path"]]},
        binding=None,
        operation_id="op-resumed-post-effect",
        replayed=False,
    )

    model = _Model()
    toolbox = _Toolbox()
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert result.success is False
    assert result.error is not None
    assert "run was closed from reconciliation evidence" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0
    assert run is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert len(attempts) == 1
    assert attempts[0].attempt_state.value == "attempt_interrupted"
    assert attempts[0].side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_rejects_step_only_truth_on_resumed_attempt_before_model(
    tmp_path: Path,
) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    tool_args = {"path": "agent_output/out.txt", "content": "ok"}
    pre_effect_turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args=tool_args)],
    )

    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=pre_effect_turn,
        context=_context(),
        prompt_hash="prompt-hash-4",
    )

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    initial_run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    initial_attempt = await control_plane.execution_repository.get_attempt_record(
        attempt_id=f"{run_id}:attempt:0001"
    )
    assert initial_run is not None
    assert initial_attempt is not None
    _, resumed_attempt = await recover_pre_effect_attempt_for_resume_mode(
        execution_repository=control_plane.execution_repository,
        publication=control_plane.publication,
        run=initial_run,
        current_attempt=initial_attempt,
    )
    assert resumed_attempt.attempt_id == initial_attempt.attempt_id
    await control_plane.execution_repository.save_step_record(
        record=StepRecord(
            step_id="op-resumed-uncertain",
            attempt_id=resumed_attempt.attempt_id,
            step_kind="governed_tool_operation",
            namespace_scope="issue:ISSUE-1",
            input_ref="turn-tool-call:resumed-uncertain",
            output_ref="turn-tool-result:op-resumed-uncertain",
            capability_used=CapabilityClass.BOUNDED_LOCAL_MUTATION,
            resources_touched=["tool:write_file", "workspace:agent_output/out.txt", "namespace:issue:ISSUE-1"],
            observed_result_classification="tool_succeeded",
            receipt_refs=["turn-tool-operation:op-resumed-uncertain"],
            closure_classification="step_completed",
        )
    )

    model = _Model()
    toolbox = _Toolbox()
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    truth = await control_plane.publication.repository.get_final_truth(run_id=run_id)

    assert result.success is False
    assert result.error is not None
    assert "run was closed from reconciliation evidence" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0
    assert run is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert len(attempts) == 1
    assert attempts[0].attempt_state.value == "attempt_interrupted"
    assert attempts[0].side_effect_boundary_class is SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
