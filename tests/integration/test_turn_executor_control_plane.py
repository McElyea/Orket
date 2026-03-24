# Layer: integration

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain import (
    CheckpointAcceptanceOutcome,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    DivergenceClass,
    RecoveryActionClass,
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
    async def complete(self, _messages):
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
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_files = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))

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
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert checkpoint.state_snapshot_ref.startswith("turn-tool-checkpoint-snapshot:")
    assert len(snapshot_files) == 1
    assert snapshot_payload["namespace_scope"] == "issue:ISSUE-1"
    assert (
        snapshot_payload["control_plane"]["resumability_class"]
        == CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT.value
    )
    assert truth.result_class.value == "success"


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
    assert run.workload_id == "governed-turn-tools"
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
    assert checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert truth.result_class.value == "success"


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_reuses_control_plane_checkpoint_and_effect_truth(tmp_path: Path) -> None:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context())
    second = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context(resume_mode=True))

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
    assert toolbox.calls == 1
    assert len(attempts) == 1
    assert len(steps) == 1
    assert len(effects) == 1
    assert len(checkpoints) == 1
    assert checkpoint_acceptance is not None
    assert checkpoint_acceptance.outcome is CheckpointAcceptanceOutcome.ACCEPTED
    assert checkpoint_acceptance.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_recovers_pre_effect_unfinished_attempt_via_new_attempt_checkpoint(
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

    toolbox = _Toolbox()
    result = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context(resume_mode=True))

    run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    run = await control_plane.execution_repository.get_run_record(run_id=run_id)
    attempts = await control_plane.execution_repository.list_attempt_records(run_id=run_id)
    first_checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run_id}:attempt:0001"
    )
    second_checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{run_id}:attempt:0002"
    )
    decision = (
        None
        if not attempts or attempts[0].recovery_decision_id is None
        else await control_plane.publication.repository.get_recovery_decision(
            decision_id=attempts[0].recovery_decision_id
        )
    )

    assert result.success is True
    assert toolbox.calls == 1
    assert run is not None
    assert len(attempts) == 2
    assert attempts[0].attempt_state.value == "attempt_interrupted"
    assert attempts[1].attempt_state.value == "attempt_completed"
    assert first_checkpoint is not None
    assert first_checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert second_checkpoint is not None
    assert second_checkpoint.resumability_class is CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT
    assert decision is not None
    assert decision.authorized_next_action is RecoveryActionClass.RESUME_FROM_CHECKPOINT
    assert decision.failed_attempt_id == attempts[0].attempt_id
    assert decision.new_attempt_id == attempts[1].attempt_id
    assert decision.target_checkpoint_id == first_checkpoint.checkpoint_id
    assert first_checkpoint.state_snapshot_ref in decision.required_precondition_refs


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
