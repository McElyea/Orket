# Layer: integration

from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.application.workflows.protocol_hashing import build_step_id, derive_operation_id
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_executor_control_plane import write_turn_checkpoint_and_publish_if_needed
from orket.core.contracts import StepRecord
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    EvidenceSufficiencyClassification,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
    SideEffectBoundaryClass,
)
from orket.core.domain.control_plane_effect_journal import create_effect_journal_entry
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


def _context(*, resume_mode: bool = False) -> dict[str, object]:
    return {
        "session_id": "run-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "in_progress",
        "selected_model": "dummy",
        "turn_index": 1,
        "history": [],
        "resume_mode": resume_mode,
        "protocol_governed_enabled": True,
    }


def _run_id() -> str:
    return "turn-tool-run:run-1:ISSUE-1:developer:0001"


def _attempt_id() -> str:
    return f"{_run_id()}:attempt:0001"


def _operation_id() -> str:
    return derive_operation_id(run_id="run-1", step_id=build_step_id(issue_id="ISSUE-1", turn_index=1), tool_index=0)


def _turn_dir(tmp_path: Path) -> Path:
    return Path(tmp_path) / "observability" / "run-1" / "ISSUE-1" / "001_developer"


def _snapshot_path(tmp_path: Path) -> Path:
    return sorted(_turn_dir(tmp_path).glob("control_plane_checkpoint_snapshot_*.json"))[0]


def _executor(tmp_path: Path) -> tuple[object, TurnExecutor]:
    control_plane = build_turn_tool_control_plane_service(tmp_path / "control_plane.sqlite3")
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=Path(tmp_path)),
        workspace=Path(tmp_path),
        control_plane_service=control_plane,
    )
    return control_plane, executor


async def _seed_checkpoint_only(tmp_path: Path):
    control_plane, executor = _executor(tmp_path)
    tool_args = {"path": "agent_output/out.txt", "content": "ok"}
    turn = ExecutionTurn(
        role="developer",
        issue_id="ISSUE-1",
        content="",
        tool_calls=[ToolCall(tool="write_file", args=tool_args)],
    )
    await write_turn_checkpoint_and_publish_if_needed(
        executor=executor,
        turn=turn,
        context=_context(),
        prompt_hash="prompt-hash-seeded",
    )
    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())
    checkpoint = await control_plane.publication.repository.get_checkpoint(
        checkpoint_id=f"turn-tool-checkpoint:{_attempt_id()}"
    )
    assert run is not None
    assert attempt is not None
    assert checkpoint is not None
    return control_plane, executor, run, attempt, checkpoint, tool_args


async def _mark_completed_success(control_plane, run, attempt, authoritative_result_ref: str) -> None:
    truth = await control_plane.publication.publish_final_truth(
        final_truth_record_id=f"turn-tool-final-truth:{run.run_id}",
        run_id=run.run_id,
        result_class=ResultClass.SUCCESS,
        completion_classification=CompletionClassification.SATISFIED,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.NONE,
        degradation_classification=DegradationClassification.NONE,
        closure_basis=ClosureBasisClassification.NORMAL_EXECUTION,
        authority_sources=[
            AuthoritySourceClass.RECEIPT_EVIDENCE,
            AuthoritySourceClass.VALIDATED_ARTIFACT,
        ],
        authoritative_result_ref=authoritative_result_ref,
    )
    await control_plane.execution_repository.save_attempt_record(
        record=attempt.model_copy(update={"attempt_state": AttemptState.COMPLETED, "end_timestamp": attempt.start_timestamp})
    )
    await control_plane.execution_repository.save_run_record(
        record=run.model_copy(update={"lifecycle_state": RunState.COMPLETED, "final_truth_record_id": truth.final_truth_record_id})
    )


async def _seed_completed_run_without_effect(tmp_path: Path):
    control_plane, executor, run, attempt, _, tool_args = await _seed_checkpoint_only(tmp_path)
    operation_id = _operation_id()
    tool_call_digest = "manual-call-digest"
    executor.artifact_writer.persist_operation_result(
        session_id="run-1",
        issue_id="ISSUE-1",
        role_name="developer",
        turn_index=1,
        operation_id=operation_id,
        tool_name="write_file",
        tool_args=tool_args,
        result={"ok": True, "tool": "write_file", "touched_paths": [tool_args["path"]]},
    )
    step = StepRecord(
        step_id=operation_id,
        attempt_id=attempt.attempt_id,
        step_kind="governed_tool_operation",
        namespace_scope="issue:ISSUE-1",
        input_ref=f"turn-tool-call:{tool_call_digest}",
        output_ref=f"turn-tool-result:{operation_id}",
        capability_used=CapabilityClass.BOUNDED_LOCAL_MUTATION,
        resources_touched=["tool:write_file", "workspace:agent_output/out.txt", "namespace:issue:ISSUE-1"],
        observed_result_classification="tool_succeeded",
        receipt_refs=[f"turn-tool-operation:{operation_id}", f"turn-tool-call:{tool_call_digest}"],
        closure_classification="step_completed",
    )
    await control_plane.execution_repository.save_step_record(record=step)
    await _mark_completed_success(control_plane, run, attempt, authoritative_result_ref=step.output_ref or operation_id)
    return control_plane, executor, step, tool_args


@pytest.mark.asyncio
async def test_completed_governed_reentry_requires_effect_journal_truth(tmp_path: Path) -> None:
    _control_plane, executor, _step, _tool_args = await _seed_completed_run_without_effect(tmp_path)
    model = _Model()
    toolbox = _Toolbox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())

    assert result.success is False
    assert result.error is not None
    assert "durable effect truth does not match checkpoint tool plan" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_completed_governed_reentry_requires_effect_alignment_with_step_truth(tmp_path: Path) -> None:
    control_plane, executor, step, _tool_args = await _seed_completed_run_without_effect(tmp_path)
    operation_id = _operation_id()
    effect = create_effect_journal_entry(
        journal_entry_id=f"turn-tool-journal:{operation_id}",
        effect_id=f"turn-tool-effect:{operation_id}",
        run_id=_run_id(),
        attempt_id=_attempt_id(),
        step_id=operation_id,
        authorization_basis_ref="turn-tool-authorization:manual-call-digest",
        publication_timestamp="2026-03-24T00:00:00+00:00",
        intended_target_ref="tool:write_file",
        observed_result_ref="turn-tool-result:wrong-op",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref=f"turn-tool-operation:{operation_id}",
    )
    await control_plane.publication.repository.append_effect_journal_entry(run_id=_run_id(), entry=effect)
    model = _Model()
    toolbox = _Toolbox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())

    assert step.output_ref == f"turn-tool-result:{operation_id}"
    assert result.success is False
    assert result.error is not None
    assert "effect truth for" in result.error
    assert "does not align with durable output truth" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0


@pytest.mark.asyncio
async def test_completed_governed_reentry_rejects_unexpected_operation_artifacts(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    executor.artifact_writer.persist_operation_result(
        session_id="run-1",
        issue_id="ISSUE-1",
        role_name="developer",
        turn_index=1,
        operation_id="unexpected-op",
        tool_name="write_file",
        tool_args={"path": "agent_output/extra.txt", "content": "extra"},
        result={"ok": True, "tool": "write_file", "touched_paths": ["agent_output/extra.txt"]},
    )

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())

    assert first.success is True
    assert second.success is False
    assert second.error is not None
    assert "durable operation artifacts do not match checkpoint tool plan" in second.error
    assert model.calls == 1
    assert toolbox.calls == 1
    assert control_plane is not None


@pytest.mark.asyncio
async def test_resume_mode_rejects_orphan_operation_artifacts_before_model(tmp_path: Path) -> None:
    control_plane, executor, _run, _attempt, _checkpoint, tool_args = await _seed_checkpoint_only(tmp_path)
    executor.artifact_writer.persist_operation_result(
        session_id="run-1",
        issue_id="ISSUE-1",
        role_name="developer",
        turn_index=1,
        operation_id=_operation_id(),
        tool_name="write_file",
        tool_args=tool_args,
        result={"ok": True, "tool": "write_file", "touched_paths": [tool_args["path"]]},
    )
    model = _Model()
    toolbox = _Toolbox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))
    run = await control_plane.execution_repository.get_run_record(run_id=_run_id())
    attempt = await control_plane.execution_repository.get_attempt_record(attempt_id=_attempt_id())
    truth = await control_plane.publication.repository.get_final_truth(run_id=_run_id())

    assert result.success is False
    assert result.error is not None
    assert "durable operation artifacts without matching control-plane step/effect truth" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0
    assert run is not None
    assert attempt is not None
    assert truth is not None
    assert run.lifecycle_state is RunState.FAILED_TERMINAL
    assert attempt.attempt_state is AttemptState.INTERRUPTED
    assert attempt.side_effect_boundary_class is SideEffectBoundaryClass.EFFECT_BOUNDARY_UNCERTAIN
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED


@pytest.mark.asyncio
async def test_completed_governed_reentry_requires_snapshot_identity_alignment(tmp_path: Path) -> None:
    control_plane, executor = _executor(tmp_path)
    model = _Model()
    toolbox = _Toolbox()

    first = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())
    snapshot_path = _snapshot_path(tmp_path)
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_payload["namespace_scope"] = "issue:OTHER"
    snapshot_path.write_text(json.dumps(snapshot_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    second = await executor.execute_turn(_issue(), _role(), model, toolbox, _context())

    assert first.success is True
    assert second.success is False
    assert second.error is not None
    assert "snapshot namespace scope does not match current request" in second.error
    assert model.calls == 1
    assert toolbox.calls == 1
    assert control_plane is not None


@pytest.mark.asyncio
async def test_resume_mode_requires_snapshot_identity_alignment(tmp_path: Path) -> None:
    _control_plane, executor, _run, _attempt, _checkpoint, _tool_args = await _seed_checkpoint_only(tmp_path)
    snapshot_path = _snapshot_path(tmp_path)
    snapshot_payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_payload["namespace_scope"] = "issue:OTHER"
    snapshot_path.write_text(json.dumps(snapshot_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    model = _Model()
    toolbox = _Toolbox()

    result = await executor.execute_turn(_issue(), _role(), model, toolbox, _context(resume_mode=True))

    assert result.success is False
    assert result.error is not None
    assert "snapshot namespace scope does not match current request" in result.error
    assert model.calls == 0
    assert toolbox.calls == 0
