"""A real failed read is retained as failure while the card is safely requeued."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from orket.adapters.tools.families.cards import CardManagementTools
from orket.application.services.card_completion_turn_service import prepare_card_completion_turn
from orket.application.services.orchestrator_issue_control_plane_support import run_id_for_dispatch
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.workflows.orchestrator import Orchestrator
from orket.core.contracts.card_completion_commit import CardCompletionRejected
from orket.core.domain import CompletionClassification
from orket.exceptions import CatastrophicFailure, ExecutionFailed
from orket.schema import CardStatus, IssueConfig
from tests.helpers.turn_artifacts import artifact_test_utc_now
from tests.integration.test_card_completion_control_plane import _runtime

pytestmark = pytest.mark.integration


class MissingReadModel:
    async def complete(self, messages):
        return {"content": json.dumps({"content": "", "tool_calls": [
            {"tool": "read_file", "args": {"path": "agent_output/absent.txt"}},
            {"tool": "add_issue_comment", "args": {"comment": "Attempted review of agent_output/absent.txt"}},
        ]}), "raw": {"total_tokens": 1}}


async def failed_read_runtime(tmp_path, protocol, status, max_retries):
    repo, service, toolbox, plane, executor, issue, role, context = await _runtime(tmp_path, protocol)
    await repo.update_status(issue.id, status)
    record = await repo.get_by_id(issue.id)
    record.max_retries = max_retries
    await repo.save(record)
    issue = IssueConfig.model_validate(record.model_dump())
    orch = Orchestrator(workspace=tmp_path / "workspace", async_cards=repo, snapshots=None,
                        org=SimpleNamespace(process_rules={}), config_root=tmp_path, db_path=repo.db_path,
                        loader=None, sandbox_orchestrator=None, card_completion=service,
        architecture_policy=ArchitecturePolicySnapshot(False),
     turn_clock=artifact_test_utc_now)
    await orch._request_issue_transition(issue=issue, target_status=status, reason="turn_dispatch",
                                         assignee="integrity_guard", roles=["integrity_guard"],
                                         metadata={"run_id": "session", "turn_index": 1, "review_turn": True})
    context["current_status"] = status.value
    await prepare_card_completion_turn(service=service, cards=repo, context=context, card_id=issue.id,
                                       session_id="session", seat_name="integrity_guard", turn_index=1)
    role.tools = ["read_file", "update_issue_status", "add_issue_comment"]
    result = await executor.execute_turn(issue, role, MissingReadModel(), toolbox, context)
    assert not result.success and "Tool read_file failed: File not found" in result.error
    assert len(await repo.get_comments(issue.id)) == 1
    return orch, repo, context, issue, result


@pytest.mark.asyncio
@pytest.mark.parametrize("protocol", [True, False], ids=["protocol", "non_protocol"])
@pytest.mark.parametrize("status", [CardStatus.IN_PROGRESS, CardStatus.CODE_REVIEW, CardStatus.AWAITING_GUARD_REVIEW])
# Layer: integration
async def test_failed_tool_requeues_without_completion_or_stale_attempt_reuse(tmp_path, protocol, status):
    orch, repo, context, issue, result = await failed_read_runtime(tmp_path, protocol, status, 3)
    old_context, old_request = context["card_completion_context"], context["card_completion_request"]
    assert old_request is not None
    with pytest.raises(ExecutionFailed, match="Orchestration Turn Failed \\(Retry 1/3\\)"):
        await orch._handle_failure(issue, result, "session", ["integrity_guard"], turn_index=1)
    stored = await repo.get_by_id(issue.id)
    assert stored.status == CardStatus.READY and stored.retry_count == 1
    assert stored.completion_context is None and stored.completion_ref is None
    assert stored.completion_generation > old_context.generation
    with pytest.raises(CardCompletionRejected):
        await repo.update_status(issue.id, CardStatus.DONE, completion_request=old_request)
    run_id = run_id_for_dispatch(session_id="session", issue_id=issue.id, seat_name="integrity_guard", turn_index=1)
    truth = await orch.control_plane_repository.get_final_truth(run_id=run_id)
    assert truth.result_class.value == "failed" and truth.completion_classification == CompletionClassification.UNSATISFIED
    await orch._request_issue_transition(issue=IssueConfig.model_validate(stored.model_dump()),
                                         target_status=CardStatus.IN_PROGRESS, reason="turn_dispatch", assignee="coder",
                                         metadata={"run_id": "session", "turn_index": 2}, roles=["coder"])
    new_context = await orch.card_completion.begin_attempt(repo, card_id=issue.id, run_id="retry-run", attempt_id="retry-2")
    assert new_context.generation > old_context.generation and new_context.digest != old_context.digest


@pytest.mark.asyncio
# Layer: integration
async def test_exhausted_guard_retry_blocks_and_retains_failed_truth(tmp_path, fresh_runtime_state):
    orch, repo, _, issue, result = await failed_read_runtime(tmp_path, True, CardStatus.AWAITING_GUARD_REVIEW, 0)
    with pytest.raises(CatastrophicFailure, match="MAX RETRIES EXCEEDED"):
        await orch._handle_failure(issue, result, "session", ["integrity_guard"], turn_index=1)
    stored = await repo.get_by_id(issue.id)
    assert stored.status == CardStatus.BLOCKED and stored.retry_count == 1
    assert await repo.read_completion_receipt(issue.id) is None
    run_id = run_id_for_dispatch(session_id="session", issue_id=issue.id, seat_name="integrity_guard", turn_index=1)
    truth = await orch.control_plane_repository.get_final_truth(run_id=run_id)
    assert truth.result_class.value == "blocked" and truth.completion_classification == CompletionClassification.UNSATISFIED


@pytest.mark.asyncio
# Layer: integration
async def test_model_status_tool_cannot_claim_system_retry_authority(tmp_path):
    repo, _, _, _, _, _, _, _ = await _runtime(tmp_path, True)
    await repo.update_status("card", CardStatus.AWAITING_GUARD_REVIEW)
    tools = CardManagementTools(tmp_path / "workspace", [], cards_repo=repo, db_path=repo.db_path)
    before = await repo.get_by_id("card")
    result = await tools.update_issue_status(
        {"status": "ready", "reason": "retry_scheduled", "action": "system_set_status"},
        {"issue_id": "card", "roles": ["integrity_guard"]})
    assert result["ok"] is False and result["error_code"] == "POLICY_VIOLATION"
    assert await repo.get_by_id("card") == before
