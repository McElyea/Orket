"""Real failure publication and SQLite success inspection through captured evaluator inputs."""
import asyncio
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.failure_report_service import FailureReportService
from orket.application.services.orchestrator_failure_handler import OrchestratorFailureHandler
from orket.application.services.orchestrator_turn_success_handler import OrchestratorTurnSuccessHandler
from orket.core.domain.execution import ExecutionTurn
from orket.schema import CardStatus, IssueConfig

pytestmark = pytest.mark.integration


class StopEvaluation(RuntimeError):
    pass


def _unexpected(*args, **kwargs):
    raise AssertionError("Unexpected post-evaluation effect")


def _failure_handler(tmp_path, node):
    return OrchestratorFailureHandler(workspace_root=tmp_path, report_timestamp="2026-09-20T00:00:00Z",
        async_cards=None, evaluator_node=node, request_issue_transition=_unexpected,
        is_issue_idesign_enabled=_unexpected, normalize_governance_violation_message=_unexpected)


@pytest.mark.asyncio
async def test_failure_input_mutation_is_refused_after_truthful_failure_publication(tmp_path):
    issue = IssueConfig(id="card", summary="Original", retry_count=1, max_retries=3)
    result = SimpleNamespace(error="Original error", violations=["Original violation"])

    class Mutation:
        def evaluate_failure(self, inputs):
            inputs.max_retries = 999

    with pytest.raises(ValidationError, match="frozen_instance"):
        await _failure_handler(tmp_path, Mutation()).handle(issue=issue, result=result, run_id="run", roles=["coder"])
    assert issue.max_retries == 3 and issue.retry_count == 1 and result.violations == ["Original violation"]
    report = json.loads(await asyncio.to_thread((tmp_path / "agent_output/policy_violation_card.json").read_text))
    assert report["detail"] == "Original error" and report["card_id"] == "card"


@pytest.mark.asyncio
async def test_report_await_preserves_admitted_failure_context_and_node(tmp_path, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()
    publish = FailureReportService.publish

    async def held(owner, report):
        entered.set()
        await release.wait()
        return await publish(owner, report)

    monkeypatch.setattr(FailureReportService, "publish", held)
    issue = IssueConfig(id="card", summary="Original", retry_count=1, max_retries=3)
    result = SimpleNamespace(error="Original error", violations=["Original violation"])
    seen = []

    class Observer:
        def evaluate_failure(self, inputs):
            seen.append(inputs)
            raise StopEvaluation

    handler = _failure_handler(tmp_path, Observer())
    operation = asyncio.create_task(handler.handle(issue=issue, result=result, run_id="run", roles=["coder"]))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        issue.retry_count, result.error = 2, "Changed error"
        result.violations.clear()
        handler.evaluator_node = SimpleNamespace(evaluate_failure=_unexpected)
        release.set()
        with pytest.raises(StopEvaluation):
            await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert (seen[0].retry_count, seen[0].error, seen[0].violations) == (1, "Original error", ("Original violation",))


async def _success_context(tmp_path, node):
    cards = AsyncCardRepository(tmp_path / "cards.sqlite3")
    issue = IssueConfig(id="card", summary="Original", seat="developer")
    await cards.save(issue.model_dump())
    turn = ExecutionTurn(role="coder", issue_id="card", content="Original response", timestamp=None)
    transcript = []
    handler = OrchestratorTurnSuccessHandler(workspace_root=tmp_path, transcript=transcript,
        async_cards=cards, memory=None, evaluator_node=node, issue_control_plane=None,
        request_issue_transition=_unexpected, trigger_sandbox=_unexpected, is_sandbox_disabled=_unexpected,
        save_checkpoint=_unexpected, create_pending_gate_request=_unexpected,
        validate_guard_rejection_payload=_unexpected, extract_guard_review_payload=_unexpected,
        resolve_guard_event=_unexpected, handle_failure=_unexpected)
    arguments = dict(issue=issue, result=SimpleNamespace(turn=turn), provider=None, run_id="run", seat_name="developer",
        roles_to_load=["coder"], turn_index=1, turn_status=CardStatus.IN_PROGRESS, is_guard_turn=False,
        is_review_turn=False, epic=None, team=None, env=None, active_build="build", context={})
    return handler, arguments, cards, transcript


@pytest.mark.asyncio
async def test_success_node_cannot_rewrite_retained_turn_or_issue(tmp_path):
    class Mutation:
        def evaluate_success(self, inputs):
            inputs.turn.content = "Rewritten response"

    handler, arguments, cards, transcript = await _success_context(tmp_path, Mutation())
    with pytest.raises(ValidationError, match="frozen_instance"):
        await handler.handle(**arguments)
    assert arguments["result"].turn.content == transcript[0].content == "Original response"
    assert arguments["issue"].status == (await cards.get_by_id("card")).status == CardStatus.READY


@pytest.mark.asyncio
async def test_success_context_and_node_are_captured_before_database_await(tmp_path, monkeypatch):
    entered, release, seen = asyncio.Event(), asyncio.Event(), []

    class Observer:
        def evaluate_success(self, inputs):
            seen.append(inputs)
            raise StopEvaluation

    handler, arguments, cards, _ = await _success_context(tmp_path, Observer())
    read = cards.get_by_id

    async def held(card_id):
        entered.set()
        await release.wait()
        return await read(card_id)

    monkeypatch.setattr(cards, "get_by_id", held)
    operation = asyncio.create_task(handler.handle(**arguments))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        arguments["issue"].status = CardStatus.BLOCKED
        arguments["result"].turn.content = "Changed externally"
        handler.evaluator_node = SimpleNamespace(evaluate_success=_unexpected)
        release.set()
        with pytest.raises(StopEvaluation):
            await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert seen[0].turn.content == "Original response" and seen[0].turn.issue_status == CardStatus.READY
    assert seen[0].updated_issue_status == CardStatus.READY
