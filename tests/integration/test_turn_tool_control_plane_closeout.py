# Layer: integration

from __future__ import annotations

from pathlib import Path

import pytest

from orket.application.services.turn_tool_control_plane_resource_lifecycle import (
    lease_id_for_run,
    reservation_id_for_run,
)
from orket.application.services.turn_tool_control_plane_service import (
    TurnToolControlPlaneError,
    build_turn_tool_control_plane_service,
)
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
from orket.core.contracts import StepRecord
from orket.core.domain import (
    CapabilityClass,
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
from orket.core.domain.execution import ExecutionTurn, ToolCall
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
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


class _OkToolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        return {"ok": True, "tool": tool_name, "touched_paths": [args["path"]], "call_count": self.calls}


class _FailToolbox:
    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, tool_name, args, context=None):
        self.calls += 1
        return {"ok": False, "tool": tool_name, "error": "boom", "touched_paths": [args["path"]]}


def _issue() -> IssueConfig:
    return IssueConfig(id="ISSUE-1", summary="Implement feature", seat="developer", status=CardStatus.IN_PROGRESS)


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


def _context(**overrides: object) -> dict[str, object]:
    context: dict[str, object] = {
        "session_id": "run-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
        "protocol_governed_enabled": True,
    }
    context.update(overrides)
    return context


def _run_id() -> str:
    return "turn-tool-run:run-1:ISSUE-1:developer:0001"


def _attempt_id(ordinal: int = 1) -> str:
    return f"{_run_id()}:attempt:{ordinal:04d}"


def _executor(tmp_path: Path):
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    return control_plane, executor


async def _recovery_decision(control_plane, attempt_id: str):
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=attempt_id)
    if attempt is None or attempt.recovery_decision_id is None:
        return None
    return await control_plane.publication.repository.get_recovery_decision(
        decision_id=attempt.recovery_decision_id
    )


@pytest.mark.asyncio
async def test_turn_executor_skill_contract_failure_publishes_terminal_recovery_decision(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)

    result = await executor.execute_turn(
        _issue(),
        _role(),
        _Model(),
        _OkToolbox(),
        _context(skill_contract_enforced=True, protocol_governed_enabled=False),
    )

    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())
    truth = await control_plane.publication.repository.get_final_truth(run_id=_run_id())
    decision = await _recovery_decision(control_plane, _attempt_id())

    assert result.success is False
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert decision is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state.value == "attempt_failed"
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.PRE_EFFECT_FAILURE
    assert RecoveryActionClass.RESUME_FROM_CHECKPOINT.value in decision.blocked_actions
    assert f"turn-tool-checkpoint:{_attempt_id()}" in decision.required_precondition_refs
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP


@pytest.mark.asyncio
async def test_turn_executor_post_effect_tool_failure_publishes_terminal_recovery_decision(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    toolbox = _FailToolbox()

    result = await executor.execute_turn(_issue(), _role(), _Model(), toolbox, _context())

    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())
    truth = await control_plane.publication.repository.get_final_truth(run_id=_run_id())
    decision = await _recovery_decision(control_plane, _attempt_id())
    reservation = await control_plane.publication.repository.get_latest_reservation_record(
        reservation_id=reservation_id_for_run(run_id=_run_id())
    )
    lease = await control_plane.publication.repository.get_latest_lease_record(
        lease_id=lease_id_for_run(run_id=_run_id())
    )

    assert result.success is False
    assert toolbox.calls == 1
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert decision is not None
    assert reservation is not None
    assert lease is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state.value == "attempt_failed"
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.POST_EFFECT_OBSERVED
    assert decision.rationale_ref.startswith("turn-tool-journal:")
    assert RecoveryActionClass.REQUIRE_RECONCILIATION_THEN_DECIDE.value in decision.blocked_actions
    assert truth.result_class is ResultClass.FAILED
    assert truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION
    assert reservation.status is ReservationStatus.PROMOTED_TO_LEASE
    assert lease.status is LeaseStatus.RELEASED


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_interrupts_effect_boundary_uncertain_attempt(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-uncertain",
    )
    await control_plane.execution_repository.save_step_record(
        record=StepRecord(
            step_id="op-uncertain",
            attempt_id=_attempt_id(),
            step_kind="governed_tool_operation",
            namespace_scope="issue:ISSUE-1",
            input_ref="turn-tool-call:uncertain",
            output_ref="turn-tool-result:op-uncertain",
            capability_used=CapabilityClass.BOUNDED_LOCAL_MUTATION,
            resources_touched=["tool:write_file", "workspace:agent_output/out.txt", "namespace:issue:ISSUE-1"],
            observed_result_classification="tool_succeeded",
            receipt_refs=["turn-tool-operation:op-uncertain"],
            closure_classification="step_completed",
        )
    )

    result = await executor.execute_turn(_issue(), _role(), _Model(), _OkToolbox(), _context(resume_mode=True))

    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())
    truth = await control_plane.publication.repository.get_final_truth(run_id=_run_id())
    decision = await _recovery_decision(control_plane, _attempt_id())
    reconciliation = (
        None
        if decision is None
        else await control_plane.publication.repository.get_reconciliation_record(
            reconciliation_id=decision.rationale_ref
        )
    )

    assert result.success is False
    assert result.error is not None
    assert "run was closed from reconciliation evidence" in result.error
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert decision is not None
    assert reconciliation is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state.value == "attempt_interrupted"
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
    assert decision.authorized_next_action is RecoveryActionClass.TERMINATE_RUN
    assert decision.side_effect_boundary_class is SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
    assert decision.rationale_ref == reconciliation.reconciliation_id
    assert reconciliation.reconciliation_id in decision.required_precondition_refs
    assert reconciliation.divergence_class is DivergenceClass.INSUFFICIENT_OBSERVATION
    assert reconciliation.safe_continuation_class is SafeContinuationClass.UNSAFE_TO_CONTINUE
    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
    assert truth.authoritative_result_ref == reconciliation.reconciliation_id


@pytest.mark.asyncio
async def test_turn_control_plane_rejects_regular_begin_after_reconciliation_closed_terminal_run(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-pending",
    )
    await control_plane.publish_step_result(
        run_id=_run_id(),
        attempt_id=_attempt_id(),
        step_id="op-post-effect",
        tool_name="write_file",
        tool_args={"path": "agent_output/out.txt", "content": "ok"},
        result={"ok": True, "touched_paths": ["agent_output/out.txt"]},
        binding=None,
        operation_id="op-post-effect",
        replayed=False,
    )
    failed = await executor.execute_turn(_issue(), _role(), _Model(), _OkToolbox(), _context(resume_mode=True))

    assert failed.success is False
    with pytest.raises(TurnToolControlPlaneError, match="already closed with blocked via reconciliation_closed"):
        await control_plane.begin_execution(
            session_id="run-1",
            issue_id="ISSUE-1",
            role_name="developer",
            turn_index=1,
            proposal_hash="sha256:proposal",
            resume_mode=False,
        )


@pytest.mark.asyncio
async def test_turn_executor_resume_mode_fails_closed_after_reconciliation_closed_terminal_run(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    class _CountingModel:
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

    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-terminal-retry",
    )
    await control_plane.publish_step_result(
        run_id=_run_id(),
        attempt_id=_attempt_id(),
        step_id="op-terminal",
        tool_name="write_file",
        tool_args={"path": "agent_output/out.txt", "content": "ok"},
        result={"ok": True, "touched_paths": ["agent_output/out.txt"]},
        binding=None,
        operation_id="op-terminal",
        replayed=False,
    )

    first = await executor.execute_turn(_issue(), _role(), _Model(), _OkToolbox(), _context(resume_mode=True))
    model = _CountingModel()
    toolbox = _OkToolbox()
    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))

    assert first.success is False
    assert second.success is False
    assert second.error is not None
    assert "already closed with blocked via reconciliation_closed" in second.error
    assert model.calls == 0
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_turn_executor_recovery_pending_run_fails_before_model_and_checkpoint_rewrite(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)

    class _CountingModel:
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

    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-recovery-pending",
    )
    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    assert run is not None
    await control_plane.execution_repository.save_run_record(
        record=run.model_copy(update={"lifecycle_state": RunState.RECOVERY_PENDING})
    )
    turn_dir = Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"
    snapshot_files_before = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))

    model = _CountingModel()
    toolbox = _OkToolbox()
    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=False))

    snapshot_files_after = sorted(turn_dir.glob("control_plane_checkpoint_snapshot_*.json"))
    assert result.success is False
    assert result.error is not None
    assert "explicit recovery or closure is required before execution can continue" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0
    assert snapshot_files_after == snapshot_files_before


@pytest.mark.asyncio
async def test_turn_control_plane_allows_same_attempt_writes_after_checkpoint_recovery(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args={"path": "agent_output/out.txt", "content": "ok"})],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-recovery",
    )
    await control_plane.begin_execution(
        session_id="run-1",
        issue_id="ISSUE-1",
        role_name="developer",
        turn_index=1,
        proposal_hash="sha256:proposal",
        resume_mode=True,
    )
    step, effect = await control_plane.publish_step_result(
        run_id=_run_id(),
        attempt_id=_attempt_id(),
        step_id="op-same-attempt",
        tool_name="write_file",
        tool_args={"path": "agent_output/out.txt", "content": "ok"},
        result={"ok": True, "touched_paths": ["agent_output/out.txt"]},
        binding=None,
        operation_id="op-same-attempt",
        replayed=False,
    )
    run, attempt, truth = await control_plane.finalize_execution(
        run_id=_run_id(),
        attempt_id=_attempt_id(),
        authoritative_result_ref="turn-tool-result:op-same-attempt",
        violation_reasons=[],
        executed_step_count=1,
    )

    assert step.attempt_id == _attempt_id()
    assert effect.attempt_id == _attempt_id()
    assert attempt.attempt_id == _attempt_id()
    assert attempt.attempt_state.value == "attempt_completed"
    assert run.lifecycle_state is RunState.COMPLETED
    assert truth.result_class is ResultClass.SUCCESS
