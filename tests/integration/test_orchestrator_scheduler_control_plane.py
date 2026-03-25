# Layer: integration

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.orchestrator_issue_control_plane_support import (
    child_workload_run_id_for_issue_creation,
    lease_id_for_run,
    scheduler_run_id_for_transition,
)
from orket.application.workflows.orchestrator import Orchestrator
from orket.core.domain import AttemptState, LeaseStatus, ReservationKind, ReservationStatus, RunState
from orket.schema import CardStatus, EnvironmentConfig, IssueConfig, SeatConfig, TeamConfig


pytestmark = pytest.mark.integration


class _Snapshots:
    async def record(self, _session_id: str, _config: dict, _logs: list[dict]) -> None:
        return None


class _Loader:
    def load_asset(self, _category: str, _name: str, _model):
        raise AssertionError("asset loading should not be reached in this test")


class _Sandbox:
    def __init__(self) -> None:
        self.registry = SimpleNamespace(get=lambda _sid: None)


class _LoopPolicy:
    @staticmethod
    def is_review_turn(status: CardStatus) -> bool:
        return status == CardStatus.CODE_REVIEW

    @staticmethod
    def turn_status_for_issue(_is_review_turn: bool) -> CardStatus:
        return CardStatus.IN_PROGRESS

    @staticmethod
    def role_order_for_turn(roles: list[str], _is_review_turn: bool) -> list[str]:
        return roles


def _build_orchestrator(tmp_path: Path, cards: AsyncCardRepository) -> Orchestrator:
    orch = Orchestrator(
        workspace=tmp_path,
        async_cards=cards,
        snapshots=_Snapshots(),
        org=SimpleNamespace(process_rules={}, architecture=SimpleNamespace(idesign_threshold=10)),
        config_root=tmp_path,
        db_path=str(tmp_path / "runtime.sqlite3"),
        loader=_Loader(),
        sandbox_orchestrator=_Sandbox(),
    )
    orch.loop_policy_node = _LoopPolicy()
    return orch


async def _assert_scheduler_truth(
    *,
    orch: Orchestrator,
    run_id: str,
    expected_issue_id: str,
    expected_result: str,
    expected_run_state: RunState,
) -> None:
    run = await orch.control_plane_execution_repository.get_run_record(run_id=run_id)
    attempt = await orch.control_plane_execution_repository.get_attempt_record(attempt_id=f"{run_id}:attempt:0001")
    steps = await orch.control_plane_execution_repository.list_step_records(attempt_id=f"{run_id}:attempt:0001")
    effects = await orch.control_plane_repository.list_effect_journal_entries(run_id=run_id)
    truth = await orch.control_plane_repository.get_final_truth(run_id=run_id)
    reservations = await orch.control_plane_repository.list_reservation_records(
        reservation_id=f"orchestrator-issue-scheduler-reservation:{run_id}"
    )
    if not reservations:
        reservations = await orch.control_plane_repository.list_reservation_records(
            reservation_id=f"orchestrator-child-workload-composition-reservation:{run_id}"
        )
    leases = await orch.control_plane_repository.list_lease_records(lease_id=lease_id_for_run(run_id=run_id))

    assert run is not None
    assert run.namespace_scope == f"issue:{expected_issue_id}"
    assert run.lifecycle_state is expected_run_state
    assert attempt is not None
    assert attempt.attempt_state in {AttemptState.COMPLETED, AttemptState.FAILED}
    assert len(steps) == 1
    assert steps[0].namespace_scope == f"issue:{expected_issue_id}"
    assert steps[0].resources_touched[0] == f"issue:{expected_issue_id}"
    assert len(effects) == 1
    assert effects[0].intended_target_ref == f"issue:{expected_issue_id}"
    assert truth is not None
    assert truth.result_class.value == expected_result
    assert [record.status for record in reservations] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert reservations[-1].reservation_kind is ReservationKind.NAMESPACE
    assert reservations[-1].target_scope_ref == f"namespace:issue:{expected_issue_id}"
    assert [record.status for record in leases] == [LeaseStatus.ACTIVE, LeaseStatus.RELEASED]
    assert leases[-1].resource_id == f"namespace:issue:{expected_issue_id}"


@pytest.mark.asyncio
async def test_dependency_block_propagation_publishes_scheduler_namespace_truth(tmp_path: Path) -> None:
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    parent = IssueConfig(
        id="ARC-1",
        summary="Architecture blocked",
        seat="architect",
        status=CardStatus.BLOCKED,
        build_id="build-1",
        session_id="run-dependency-block",
    )
    child = IssueConfig(
        id="COD-1",
        summary="Implementation blocked by dependency",
        seat="developer",
        status=CardStatus.READY,
        build_id="build-1",
        session_id="run-dependency-block",
        depends_on=["ARC-1"],
    )
    await cards.save(parent.model_dump())
    await cards.save(child.model_dump())
    orch = _build_orchestrator(tmp_path, cards)

    backlog = [
        IssueConfig(
            id="ARC-1",
            summary="Architecture blocked",
            seat="architect",
            status=CardStatus.BLOCKED,
            build_id="build-1",
            session_id="run-dependency-block",
        ),
        IssueConfig(
            id="COD-1",
            summary="Implementation blocked by dependency",
            seat="developer",
            status=CardStatus.READY,
            build_id="build-1",
            session_id="run-dependency-block",
            depends_on=["ARC-1"],
        ),
    ]
    propagated = await orch._propagate_dependency_blocks(backlog, "run-dependency-block")

    assert propagated == 1
    updated_child = await cards.get_by_id("COD-1")
    assert updated_child is not None
    assert updated_child.status == CardStatus.BLOCKED
    run_id = scheduler_run_id_for_transition(
        session_id="run-dependency-block",
        issue_id="COD-1",
        current_status=CardStatus.READY,
        target_status=CardStatus.BLOCKED,
        reason="dependency_blocked",
        metadata={"run_id": "run-dependency-block", "blocked_by": ["ARC-1"], "wait_reason": "dependency"},
    )
    await _assert_scheduler_truth(
        orch=orch,
        run_id=run_id,
        expected_issue_id="COD-1",
        expected_result="blocked",
        expected_run_state=RunState.FAILED_TERMINAL,
    )


@pytest.mark.asyncio
async def test_pre_dispatch_runtime_guard_retry_publishes_scheduler_effect_truth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    issue = IssueConfig(
        id="REV-1",
        summary="Review implementation",
        seat="code_reviewer",
        status=CardStatus.CODE_REVIEW,
        retry_count=0,
        max_retries=3,
        build_id="build-1",
        session_id="run-guard",
    )
    await cards.save(issue.model_dump())
    orch = _build_orchestrator(tmp_path, cards)

    class _RuntimeVerifier:
        def __init__(self, workspace_root, organization=None):
            self.workspace_root = workspace_root

        async def verify(self):
            return SimpleNamespace(
                ok=False,
                checked_files=["agent_output/main.py"],
                errors=["SyntaxError: invalid syntax"],
                command_results=[],
                failure_breakdown={},
            )

    class _Executor:
        def __init__(self) -> None:
            self.calls = 0

        async def execute_turn(self, *args, **kwargs):
            self.calls += 1
            raise AssertionError("executor should not be reached when runtime verification fails pre-dispatch")

    monkeypatch.setattr("orket.application.workflows.orchestrator.RuntimeVerifier", _RuntimeVerifier)
    executor = _Executor()

    await orch._execute_issue_turn(
        issue_data=SimpleNamespace(model_dump=lambda: issue.model_dump()),
        epic=SimpleNamespace(parent_id=None, id="EPIC-1", name="Epic 1"),
        team=TeamConfig(name="core", seats={"code_reviewer": SeatConfig(name="code_reviewer", roles=["code_reviewer"])}),
        env=EnvironmentConfig(name="dev", model="test-model"),
        run_id="run-guard",
        active_build="build-1",
        prompt_strategy_node=SimpleNamespace(
            select_model=lambda **_kwargs: "test-model",
            select_dialect=lambda _selected_model: "json",
        ),
        executor=executor,
        toolbox=SimpleNamespace(),
    )

    assert executor.calls == 0
    updated_issue = await cards.get_by_id("REV-1")
    assert updated_issue is not None
    assert updated_issue.status == CardStatus.READY
    run_id = scheduler_run_id_for_transition(
        session_id="run-guard",
        issue_id="REV-1",
        current_status=CardStatus.CODE_REVIEW,
        target_status=CardStatus.READY,
        reason="runtime_guard_retry_scheduled",
        metadata={"run_id": "run-guard", "retry_count": 1},
    )
    await _assert_scheduler_truth(
        orch=orch,
        run_id=run_id,
        expected_issue_id="REV-1",
        expected_result="failed",
        expected_run_state=RunState.FAILED_TERMINAL,
    )


@pytest.mark.asyncio
async def test_team_replan_creation_publishes_child_workload_composition_truth(tmp_path: Path) -> None:
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    trigger = IssueConfig(
        id="REQ-1",
        summary="Requirements changed",
        seat="requirements_analyst",
        status=CardStatus.READY,
        build_id="build-1",
        session_id="run-abc1",
        params={"replan_requested": True},
    )
    await cards.save(trigger.model_dump())
    orch = _build_orchestrator(tmp_path, cards)

    backlog = [trigger]
    team = TeamConfig(name="core", seats={"architect": SeatConfig(name="architect", roles=["architect"])})
    scheduled = await orch._maybe_schedule_team_replan(backlog, "run-abc1", "build-1", team)

    assert scheduled is True
    created_issue = await cards.get_by_id("REPLAN-RUN-AB-1")
    assert created_issue is not None
    assert created_issue.status == CardStatus.READY
    run_id = child_workload_run_id_for_issue_creation(
        session_id="run-abc1",
        child_issue_id="REPLAN-RUN-AB-1",
        relationship_class="team_replan",
        metadata={
            "active_build": "build-1",
            "seat_name": "coder",
            "trigger_issue_ids": ["REQ-1"],
            "replan_count": 1,
        },
    )
    await _assert_scheduler_truth(
        orch=orch,
        run_id=run_id,
        expected_issue_id="REPLAN-RUN-AB-1",
        expected_result="success",
        expected_run_state=RunState.COMPLETED,
    )
    steps = await orch.control_plane_execution_repository.list_step_records(attempt_id=f"{run_id}:attempt:0001")
    assert steps[0].step_kind == "create_child_issue"
    assert "issue:REQ-1" in steps[0].resources_touched
