# Layer: integration

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.workflows.orchestrator import Orchestrator
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.services.orchestrator_issue_control_plane_support import (
    lease_id_for_run,
    reservation_id_for_run,
    run_id_for_dispatch,
)
from orket.application.services.turn_tool_control_plane_service import build_turn_tool_control_plane_service
from orket.core.domain import AttemptState, CapabilityClass, LeaseStatus, ReservationKind, ReservationStatus, RunState
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import CardStatus, DialectConfig, EnvironmentConfig, EpicConfig, IssueConfig, RoleConfig, SeatConfig, TeamConfig


pytestmark = pytest.mark.integration


class _Snapshots:
    def __init__(self) -> None:
        self.records: list[tuple[str, dict, list[dict]]] = []

    async def record(self, session_id: str, config: dict, logs: list[dict]) -> None:
        self.records.append((session_id, config, logs))


class _Loader:
    def __init__(self, assets: list[object]) -> None:
        self._assets = list(assets)

    def load_asset(self, _category: str, _name: str, _model):
        if not self._assets:
            raise AssertionError("no queued asset")
        return self._assets.pop(0)


class _Provider:
    def __init__(self) -> None:
        self.clear_calls = 0
        self.close_calls = 0

    async def clear_context(self) -> None:
        self.clear_calls += 1

    async def close(self) -> None:
        self.close_calls += 1


class _Client:
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
            "context_namespace": None if context is None else context.get("run_namespace_scope"),
        }


def _issue() -> IssueConfig:
    return IssueConfig(
        id="ISSUE-1",
        summary="Implement feature",
        seat="developer",
        status=CardStatus.READY,
        build_id="build-1",
        session_id="run-1",
    )


def _role() -> RoleConfig:
    return RoleConfig(id="DEV", summary="developer", description="Build code", tools=["write_file"])


def _dialect() -> DialectConfig:
    return DialectConfig(
        model_family="test-model",
        dsl_format="json",
        constraints=[],
        hallucination_guard="strict",
    )


@pytest.mark.asyncio
async def test_orchestrator_issue_turn_publishes_issue_dispatch_and_non_protocol_tool_truth(tmp_path: Path) -> None:
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    issue = _issue()
    await cards.save(issue.model_dump())

    snapshots = _Snapshots()
    provider = _Provider()
    client = _Client()
    loader = _Loader([_role(), _dialect()])
    orch = Orchestrator(
        workspace=tmp_path,
        async_cards=cards,
        snapshots=snapshots,
        org=SimpleNamespace(process_rules={}, architecture=SimpleNamespace(idesign_threshold=10)),
        config_root=tmp_path,
        db_path=str(tmp_path / "runtime.sqlite3"),
        loader=loader,
        sandbox_orchestrator=SimpleNamespace(registry=SimpleNamespace(get=lambda _sid: None)),
    )
    orch.router_node = SimpleNamespace(route=lambda _issue, _team, _is_review_turn: "developer")
    orch.loop_policy_node = SimpleNamespace(
        is_review_turn=lambda _status: False,
        turn_status_for_issue=lambda _is_review_turn: CardStatus.IN_PROGRESS,
        role_order_for_turn=lambda roles, _is_review_turn: roles,
    )
    orch.evaluator_node = SimpleNamespace(
        evaluate_success=lambda **_kwargs: {},
        success_post_actions=lambda _evaluation: {},
        should_trigger_sandbox=lambda _actions: False,
        next_status_after_success=lambda _actions: None,
        evaluate_failure=lambda _issue, _result: {"action": "retry", "next_retry_count": 1},
        failure_exception_class=lambda _action: RuntimeError,
        status_for_failure_action=lambda _action: CardStatus.READY,
        failure_event_name=lambda _action: None,
        should_cancel_session=lambda _action: False,
        retry_failure_message=lambda *args: "retry failure",
        governance_violation_message=lambda error: str(error),
        catastrophic_failure_message=lambda *_args: "catastrophic failure",
        unexpected_failure_action_message=lambda action, issue_id: f"{action}:{issue_id}",
    )
    orch.model_client_node = SimpleNamespace(
        create_provider=lambda _selected_model, _env: provider,
        create_client=lambda _provider: client,
    )

    control_plane_db_path = Path(orch.control_plane_repository.db_path)
    executor = TurnExecutor(
        StateMachine(),
        ToolGate(organization=None, workspace_root=tmp_path),
        workspace=tmp_path,
        control_plane_service=build_turn_tool_control_plane_service(control_plane_db_path),
    )
    toolbox = _Toolbox()

    epic = EpicConfig(id="EPIC-1", summary="Epic", team="core", environment="dev", issues=[])
    team = TeamConfig(name="core", seats={"developer": SeatConfig(name="developer", roles=["developer"])})
    env = EnvironmentConfig(name="dev", model="test-model")

    await orch._execute_issue_turn(
        issue_data=issue,
        epic=epic,
        team=team,
        env=env,
        run_id="run-1",
        active_build="build-1",
        prompt_strategy_node=SimpleNamespace(
            select_model=lambda **_kwargs: "test-model",
            select_dialect=lambda _selected_model: "json",
        ),
        executor=executor,
        toolbox=toolbox,
    )

    issue_run_id = run_id_for_dispatch(
        session_id="run-1",
        issue_id="ISSUE-1",
        seat_name="developer",
        turn_index=1,
    )
    issue_run = await orch.control_plane_execution_repository.get_run_record(run_id=issue_run_id)
    issue_attempt = await orch.control_plane_execution_repository.get_attempt_record(
        attempt_id=f"{issue_run_id}:attempt:0001"
    )
    issue_steps = await orch.control_plane_execution_repository.list_step_records(
        attempt_id=f"{issue_run_id}:attempt:0001"
    )
    issue_effects = await orch.control_plane_repository.list_effect_journal_entries(run_id=issue_run_id)
    issue_truth = await orch.control_plane_repository.get_final_truth(run_id=issue_run_id)
    issue_reservations = await orch.control_plane_repository.list_reservation_records(
        reservation_id=reservation_id_for_run(run_id=issue_run_id)
    )
    issue_leases = await orch.control_plane_repository.list_lease_records(
        lease_id=lease_id_for_run(run_id=issue_run_id)
    )
    issue_resources = await orch.control_plane_repository.list_resource_records(
        resource_id="issue-dispatch-slot:run-1:ISSUE-1"
    )

    tool_run_id = "turn-tool-run:run-1:ISSUE-1:developer:0001"
    tool_run = await orch.control_plane_execution_repository.get_run_record(run_id=tool_run_id)
    tool_effects = await orch.control_plane_repository.list_effect_journal_entries(run_id=tool_run_id)

    assert toolbox.calls == 1
    assert client.calls == 1
    assert provider.clear_calls == 1
    assert snapshots.records

    assert issue_run is not None
    assert issue_run.lifecycle_state is RunState.COMPLETED
    assert issue_run.namespace_scope == "issue:ISSUE-1"
    assert issue_attempt is not None
    assert issue_attempt.attempt_state is AttemptState.COMPLETED
    assert len(issue_steps) == 2
    steps_by_id = {step.step_id.rsplit(":", 1)[-1]: step for step in issue_steps}
    assert steps_by_id["dispatch"].capability_used is CapabilityClass.BOUNDED_LOCAL_MUTATION
    assert steps_by_id["closeout"].capability_used is CapabilityClass.OBSERVE
    assert steps_by_id["closeout"].step_kind == "issue_status_observation"
    assert len(issue_effects) == 2
    assert issue_effects[0].step_id == steps_by_id["dispatch"].step_id
    assert issue_effects[-1].step_id == steps_by_id["closeout"].step_id
    assert issue_truth is not None
    assert issue_truth.result_class.value == "success"
    assert issue_truth.authoritative_result_ref.startswith("issue-observation:run-1:ISSUE-1:in_progress")
    assert [record.status for record in issue_reservations] == [
        ReservationStatus.ACTIVE,
        ReservationStatus.PROMOTED_TO_LEASE,
    ]
    assert issue_reservations[-1].reservation_kind is ReservationKind.CONCURRENCY
    assert issue_reservations[-1].target_scope_ref == "issue-dispatch-slot:run-1:ISSUE-1"
    assert [record.status for record in issue_leases] == [LeaseStatus.ACTIVE, LeaseStatus.RELEASED]
    assert issue_leases[-1].source_reservation_id == issue_reservations[-1].reservation_id
    assert [record.current_observed_state.split(";")[0] for record in issue_resources] == [
        "lease_status:lease_active",
        "lease_status:lease_released",
    ]

    assert tool_run is not None
    assert tool_run.namespace_scope == "issue:ISSUE-1"
    assert len(tool_effects) == 1
    assert tool_effects[0].intended_target_ref == "tool:write_file"
