"""Deterministic model requests through real verifier, turn tools and final storage."""
from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services.runtime_verifier import RuntimeVerifier
from orket.application.services.tool_gate_service import ToolGate
from orket.application.services.toolbox import ToolBox
from orket.application.workflows.turn_executor import TurnExecutor
from orket.core.domain.records import IssueRecord
from orket.core.domain.state_machine import StateMachine
from orket.schema import CardStatus, IssueConfig, RoleConfig
from tests.helpers.card_completion import completion_components, completion_definition, write_completion_source
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = pytest.mark.integration


class CompletionModel:
    def __init__(self, explicit):
        self.explicit = explicit

    async def complete(self, messages):
        calls = [{"tool": "update_issue_status", "args": {"status": "done"}}] if self.explicit else []
        return {"content": json.dumps({"content": "The work is complete.", "tool_calls": calls}),
                "raw": {"total_tokens": 1}}


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [True, False], ids=["explicit", "synthesized"])
@pytest.mark.parametrize("case", ["no_plan", "empty", "syntax_only", "wrong_behavior", "failed_command", "accepted"])
# Layer: integration
async def test_turn_completion_requires_declared_behavior_through_final_persistence(tmp_path, explicit, case):
    workspace = tmp_path / "workspace"
    await asyncio.to_thread(workspace.mkdir)
    repo, service = completion_components(tmp_path / "cards.db", workspace)
    sources = {"syntax_only": "answer = 42\n", "wrong_behavior": "print('{}')\n", "failed_command": "raise SystemExit(1)\n"}
    if case != "empty":
        if case in sources:
            await write_completion_source(workspace, sources[case])
        else:
            await write_completion_source(workspace)
    params = {} if case == "no_plan" else {"completion_acceptance": completion_definition().model_dump(mode="json")}
    record = IssueRecord(id="card", summary="Increment integers as declared", seat="integrity_guard", session_id="session",
                          status=CardStatus.CODE_REVIEW, params=params)
    await repo.save(record)
    bound = await service.begin_attempt(repo, card_id=record.id, run_id="run", attempt_id="attempt")
    evaluation = await service.evaluate_attempt(repo, bound)
    legacy = await RuntimeVerifier(workspace).verify()
    assert legacy.ok  # Empty checks and syntactically valid sources still return this legacy flag.
    context = {"session_id": "session", "issue_id": record.id, "turn_index": 1, "current_status": "code_review",
               "role": "integrity_guard", "roles": ["integrity_guard"], "required_action_tools": ["update_issue_status"],
               "required_statuses": ["done", "blocked"], "runtime_verifier_ok": legacy.ok,
               "card_completion_request": evaluation.request, "card_completion_decision": evaluation.decision}
    gate = ToolGate(organization=None, workspace_root=workspace)
    toolbox = ToolBox(None, str(workspace), [], db_path=repo.db_path, cards_repo=repo, tool_gate=gate)
    executor = TurnExecutor(StateMachine(), gate, workspace, utc_now=artifact_test_utc_now)
    role = RoleConfig(id="GUARD", summary="integrity_guard", description="Review declared acceptance", tools=["update_issue_status"])
    result = await executor.execute_turn(IssueConfig.model_validate(record.model_dump()), role,
                                         CompletionModel(explicit), toolbox, context)
    stored = await repo.get_by_id(record.id)
    if case == "accepted":
        assert result.success and stored.status == CardStatus.DONE
        assert stored.completion_ref and len(await repo.get_card_history(record.id)) == 1
        # Resume uses the same turn/tool cache identifiers after an actual reopen.
        await repo.update_status(record.id, CardStatus.CODE_REVIEW)
        await write_completion_source(workspace, "print('{}')\n")
        next_context = await service.begin_attempt(repo, card_id=record.id, run_id="next-run", attempt_id="next-attempt")
        rejected = await service.evaluate_attempt(repo, next_context)
        context.update(card_completion_request=rejected.request, card_completion_decision=rejected.decision, resume_mode=True)
        resumed = await executor.execute_turn(IssueConfig.model_validate(record.model_dump()), role,
                                              CompletionModel(True), toolbox, context)
        assert not resumed.success and (await repo.get_by_id(record.id)).status == CardStatus.CODE_REVIEW
    else:
        assert not result.success and stored.status == CardStatus.CODE_REVIEW
        assert stored.completion_ref is None and await repo.get_card_history(record.id) == []
