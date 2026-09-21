"""Actual card storage and orchestrator flows with controlled loop strategies; no inference."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.application.services.orchestrator_turn_preparation_service import OrchestratorTurnPreparationService
from orket.decision_nodes.builtins import DefaultOrchestrationLoopPolicyNode, DefaultRouterNode
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.schema import CardStatus, EnvironmentConfig
from tests.application.test_execution_pipeline_cards_epic_control_plane import _write_epic_assets
from tests.integration.test_dispatch_input_admission import _dispatch_context

pytestmark = pytest.mark.integration


class StopAtRole(RuntimeError):
    pass


@pytest.mark.asyncio
async def test_seat_policy_refuses_issue_mutation_during_actual_context_build(tmp_path):
    class Mutation(DefaultOrchestrationLoopPolicyNode):
        def required_action_tools_for_seat(self, inputs):
            inputs.issue.summary = "Replacement objective"
            return []
    repo, issue, _team, orch = await _dispatch_context(tmp_path, SimpleNamespace())
    orch.loop_policy_node = Mutation()
    with pytest.raises(ValidationError, match="frozen_instance"):
        orch._build_turn_context(run_id="run", issue=issue, seat_name="developer", roles_to_load=["coder"],
            turn_status=CardStatus.IN_PROGRESS, selected_model="fixture", resume_mode=False)
    assert issue.summary == "Original objective" and await repo.get_by_id(issue.id) == issue


@pytest.mark.asyncio
async def test_loop_advisor_cannot_mutate_inspected_backlog_or_claim_completion(test_root, workspace, db_path, monkeypatch):
    await asyncio.to_thread(_write_epic_assets, test_root, "loop_input_epic")
    team_path = test_root/"model/core/teams/standard.json"
    team = json.loads(await asyncio.to_thread(team_path.read_text, encoding="utf-8"))
    team["seats"]["code_reviewer"] = {"name": "Reviewer", "roles": ["code_reviewer"]}
    await asyncio.to_thread(team_path.write_text, json.dumps(team), encoding="utf-8")
    async with ExecutionPipeline.open(workspace, department="core", db_path=db_path, config_root=test_root) as pipeline:
        observed = []
        class Mutation(DefaultOrchestrationLoopPolicyNode):
            def no_candidate_outcome(self, inputs):
                observed.extend(inputs)
                with pytest.raises(ValidationError, match="frozen_instance"):
                    inputs[0].status = CardStatus.DONE
                return {"is_done": True, "event_name": "orchestrator_epic_complete"}
        pipeline.orchestrator.loop_policy_node = Mutation()
        execute = pipeline.orchestrator.execute_epic
        async def terminate_before_loop(**kwargs):
            await pipeline.async_cards.update_status("ISSUE-1", CardStatus.CANCELED)
            await execute(**kwargs)
        monkeypatch.setattr(pipeline.orchestrator, "execute_epic", terminate_before_loop)
        try:
            result = await pipeline.run_epic("loop_input_epic", build_id="build", session_id="loop-input-session")
            assert len(observed) == 1 and observed[0].status == CardStatus.CANCELED
            assert not result.succeeded and result.observation == "published"
            assert (await pipeline.async_cards.get_by_id("ISSUE-1")).status == CardStatus.CANCELED
            ledger = await pipeline.run_ledger.get_run("loop-input-session")
            assert ledger["status"] == "terminal_failure"
            assert ledger["artifact_json"]["card_completion_outcome"]["acceptance_satisfied"] is False
        finally:
            await pipeline.close()


@pytest.mark.asyncio
async def test_role_values_stay_bound_across_real_card_transition(tmp_path, monkeypatch):
    repo, issue, team, orch = await _dispatch_context(tmp_path, DefaultRouterNode())
    entered, release = asyncio.Event(), asyncio.Event()
    observed = []
    class Observer(DefaultOrchestrationLoopPolicyNode):
        def role_order_for_turn(self, roles, is_review_turn):
            observed.append(roles)
            with pytest.raises(AttributeError):
                roles.append("guard")
            return super().role_order_for_turn(roles, is_review_turn)
    orch.loop_policy_node = Observer()
    transition = orch._request_issue_transition
    async def held_transition(**kwargs):
        await transition(**kwargs)
        entered.set()
        await release.wait()
    async def stop_after_selection(_owner, category, name, _model_type):
        assert (category, name) == ("roles", "coder")
        raise StopAtRole("Role selected")
    monkeypatch.setattr(orch, "_request_issue_transition", held_transition)
    monkeypatch.setattr(OrchestratorTurnPreparationService, "_load_asset", stop_after_selection)
    operation = asyncio.create_task(orch._execute_issue_turn(issue, SimpleNamespace(params={}), team,
        EnvironmentConfig(name="test", model="fixture"), "run", "build", None, None, None))
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        team.seats["developer"].roles[:] = ["replacement"]
        assert (await repo.get_by_id(issue.id)).status == CardStatus.IN_PROGRESS
        release.set()
        with pytest.raises(StopAtRole, match="Role selected"):
            await asyncio.wait_for(operation, timeout=5)
        assert observed == [("coder",)]
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
