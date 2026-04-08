from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from orket.logging import log_event
from orket.schema import IssueConfig


class OrchestratorFailureHandler:
    """Owns orchestrator failure-path state transitions and exception shaping."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        transcript: list[Any],
        async_cards: Any,
        evaluator_node: Any,
        request_issue_transition: Callable[..., Awaitable[None]],
        is_issue_idesign_enabled: Callable[[IssueConfig], bool],
        normalize_governance_violation_message: Callable[[str | None], str],
    ) -> None:
        self.workspace_root = workspace_root
        self.transcript = transcript
        self.async_cards = async_cards
        self.evaluator_node = evaluator_node
        self.request_issue_transition = request_issue_transition
        self.is_issue_idesign_enabled = is_issue_idesign_enabled
        self.normalize_governance_violation_message = normalize_governance_violation_message

    @staticmethod
    def _failure_metadata(*, run_id: str, result: Any, turn_index: int | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        metadata: dict[str, Any] = {"run_id": run_id, "error": result.error}
        if turn_index is not None:
            metadata["turn_index"] = turn_index
        if extra:
            metadata.update(extra)
        return metadata

    async def _cancel_runtime_tasks(self, run_id: str) -> None:
        from orket.state import runtime_state

        tasks = await runtime_state.get_tasks(run_id)
        for task in tasks:
            if task.done():
                continue
            cancel_result = task.cancel()
            if asyncio.iscoroutine(cancel_result):
                await cancel_result

    async def handle(
        self,
        *,
        issue: IssueConfig,
        result: Any,
        run_id: str,
        roles: list[str],
        turn_index: int | None = None,
    ) -> None:
        from orket.core.domain.failure_reporter import FailureReporter

        await FailureReporter.generate_report(
            workspace=self.workspace_root,
            session_id=run_id,
            card_id=issue.id,
            violation=result.error or "Unknown failure",
            transcript=self.transcript,
            roles=roles,
        )

        eval_decision = self.evaluator_node.evaluate_failure(issue, result)
        issue.retry_count = eval_decision.get("next_retry_count", issue.retry_count)
        action = eval_decision.get("action")
        failure_exception_class = self.evaluator_node.failure_exception_class(action)

        if action == "governance_violation":
            await self.request_issue_transition(
                issue=issue,
                target_status=self.evaluator_node.status_for_failure_action(action),
                reason="governance_violation",
                metadata=self._failure_metadata(run_id=run_id, result=result, turn_index=turn_index),
                roles=roles,
            )
            await self.async_cards.save(issue.model_dump())
            message = self.evaluator_node.governance_violation_message(result.error)
            if not self.is_issue_idesign_enabled(issue):
                message = self.normalize_governance_violation_message(message)
            raise failure_exception_class(message)

        if action == "approval_pending":
            event_name = self.evaluator_node.failure_event_name(action)
            if event_name:
                log_event(
                    event_name,
                    {"run_id": run_id, "issue_id": issue.id, "error": result.error},
                    self.workspace_root,
                )
            await self.async_cards.save(issue.model_dump())
            raise failure_exception_class(str(result.error or "Approval required before execution."))

        if action == "catastrophic":
            event_name = self.evaluator_node.failure_event_name(action)
            if event_name:
                log_event(
                    event_name,
                    {"run_id": run_id, "issue_id": issue.id, "retry_count": issue.retry_count, "error": result.error},
                    self.workspace_root,
                )
            await self.request_issue_transition(
                issue=issue,
                target_status=self.evaluator_node.status_for_failure_action(action),
                reason="catastrophic_failure",
                metadata=self._failure_metadata(run_id=run_id, result=result, turn_index=turn_index),
                roles=roles,
            )
            await self.async_cards.save(issue.model_dump())
            if self.evaluator_node.should_cancel_session(action):
                await self._cancel_runtime_tasks(run_id)
            raise failure_exception_class(self.evaluator_node.catastrophic_failure_message(issue.id, issue.max_retries))

        if action != "retry":
            raise failure_exception_class(self.evaluator_node.unexpected_failure_action_message(action, issue.id))

        event_name = self.evaluator_node.failure_event_name(action)
        if event_name:
            log_event(
                event_name,
                {
                    "run_id": run_id,
                    "issue_id": issue.id,
                    "retry_count": issue.retry_count,
                    "max_retries": issue.max_retries,
                    "error": result.error,
                },
                self.workspace_root,
            )

        await self.request_issue_transition(
            issue=issue,
            target_status=self.evaluator_node.status_for_failure_action(action),
            reason="retry_scheduled",
            metadata=self._failure_metadata(
                run_id=run_id,
                result=result,
                turn_index=turn_index,
                extra={
                    "retry_count": issue.retry_count,
                    "max_retries": issue.max_retries,
                },
            ),
            roles=roles,
        )
        await self.async_cards.save(issue.model_dump())
        raise failure_exception_class(
            self.evaluator_node.retry_failure_message(
                issue.id,
                issue.retry_count,
                issue.max_retries,
                result.error,
            )
        )
