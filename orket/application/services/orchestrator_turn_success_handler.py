from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from orket.application.services.card_completion_turn_service import verify_card_completion_claims
from orket.application.services.decision_context_service import (
    admit_success_actions,
    admit_success_recommendation,
    capture_success_turn,
)
from orket.core.contracts.card_completion_commit import SUCCESSFUL_CARD_STATUSES, CardCompletionRejected
from orket.core.contracts.decision_inputs import SuccessEvaluationInput
from orket.core.domain.execution import ExecutionTurn
from orket.logging import log_event


class OrchestratorTurnSuccessHandler:
    """Owns post-dispatch success handling for orchestrator issue turns."""

    def __init__(
        self,
        *,
        workspace_root: Path,
        transcript: list[Any],
        async_cards: Any,
        memory: Any,
        evaluator_node: Any,
        issue_control_plane: Any,
        request_issue_transition: Callable[..., Awaitable[None]],
        trigger_sandbox: Callable[..., Awaitable[None]],
        is_sandbox_disabled: Callable[[], bool],
        save_checkpoint: Callable[..., Awaitable[None]],
        create_pending_gate_request: Callable[..., Awaitable[str]],
        validate_guard_rejection_payload: Callable[[Any], dict[str, Any]],
        extract_guard_review_payload: Callable[[ExecutionTurn], Any],
        resolve_guard_event: Callable[[Any], str | None],
        handle_failure: Callable[..., Awaitable[None]],
    ) -> None:
        self.workspace_root = workspace_root
        self.transcript = transcript
        self.async_cards = async_cards
        self.memory = memory
        self.evaluator_node = evaluator_node
        self.issue_control_plane = issue_control_plane
        self.request_issue_transition = request_issue_transition
        self.trigger_sandbox = trigger_sandbox
        self.is_sandbox_disabled = is_sandbox_disabled
        self.save_checkpoint = save_checkpoint
        self.create_pending_gate_request = create_pending_gate_request
        self.validate_guard_rejection_payload = validate_guard_rejection_payload
        self.extract_guard_review_payload = extract_guard_review_payload
        self.resolve_guard_event = resolve_guard_event
        self.handle_failure = handle_failure

    async def _handle_guard_turn(
        self,
        *,
        issue: Any,
        turn: ExecutionTurn,
        updated_issue: Any,
        run_id: str,
        seat_name: str,
        turn_status: Any,
        turn_index: int,
        roles_to_load: list[str],
    ) -> bool:
        guard_payload = self.extract_guard_review_payload(turn)
        guard_event = self.resolve_guard_event(updated_issue.status)
        if guard_event == "guard_rejected":
            guard_validation = self.validate_guard_rejection_payload(guard_payload)
            if not guard_validation.get("valid", False):
                request_id = await self.create_pending_gate_request(
                    run_id=run_id,
                    issue_id=issue.id,
                    seat_name=seat_name,
                    reason=str(guard_validation.get("reason") or "invalid_guard_payload"),
                    payload=guard_payload.model_dump(),
                    issue=issue,
                    turn_status=turn_status,
                )
                log_event(
                    "gate_request_created",
                    {
                        "run_id": run_id,
                        "request_id": request_id,
                        "issue_id": issue.id,
                        "seat": seat_name,
                        "request_type": "guard_rejection_payload",
                    },
                    self.workspace_root,
                )
                log_event(
                    "guard_payload_invalid",
                    {
                        "run_id": run_id,
                        "issue_id": issue.id,
                        "seat": seat_name,
                        "request_id": request_id,
                        "reason": guard_validation.get("reason"),
                        "payload": guard_payload.model_dump(),
                    },
                    self.workspace_root,
                )
                failure_result = SimpleNamespace(
                    error=(
                        "Deterministic failure: invalid guard rejection payload "
                        f"({guard_validation.get('reason')})."
                    ),
                    violations=[],
                )
                await self.handle_failure(
                    issue,
                    failure_result,
                    run_id,
                    roles_to_load,
                    turn_index=turn_index,
                )
                return False
        if guard_event:
            log_event(
                guard_event,
                {
                    "run_id": run_id,
                    "issue_id": issue.id,
                    "seat": seat_name,
                    "review_payload": guard_payload.model_dump(),
                },
                self.workspace_root,
            )
            log_event(
                "guard_review_payload",
                {
                    "run_id": run_id,
                    "issue_id": issue.id,
                    "payload": guard_payload.model_dump(),
                },
                self.workspace_root,
            )
        return True

    async def handle(
        self,
        *,
        issue: Any,
        result: Any,
        provider: Any,
        run_id: str,
        seat_name: str,
        roles_to_load: list[str],
        turn_index: int,
        turn_status: Any,
        is_guard_turn: bool,
        is_review_turn: bool,
        epic: Any,
        team: Any,
        env: Any,
        active_build: str,
        context: dict[str, Any],
    ) -> None:
        turn_inputs = capture_success_turn(issue, result.turn, seat_name, is_review_turn)
        node = self.evaluator_node
        self.transcript.append(result.turn)
        updated_issue = await self.async_cards.get_by_id(issue.id)
        evaluation = SuccessEvaluationInput(turn=turn_inputs, updated_issue_status=updated_issue.status)
        await verify_card_completion_claims(cards=self.async_cards, turn=result.turn, context=context)
        receipt = None
        if updated_issue.status.value in SUCCESSFUL_CARD_STATUSES:
            receipt = await self.async_cards.read_completion_receipt(issue.id)
            if receipt is None:
                raise CardCompletionRejected("E_CARD_COMPLETION_RESULT_UNVERIFIED")
        if is_guard_turn:
            should_continue = await self._handle_guard_turn(
                issue=issue,
                turn=result.turn,
                updated_issue=updated_issue,
                run_id=run_id,
                seat_name=seat_name,
                turn_status=turn_status,
                turn_index=turn_index,
                roles_to_load=roles_to_load,
            )
            if not should_continue:
                return

        success_eval = admit_success_recommendation(node.evaluate_success(evaluation))
        if success_eval.get("remember_decision"):
            await self.memory.remember(
                content=f"Decision by {seat_name} on {issue.id}: {turn_inputs.content[:200]}...",
                metadata={
                    "issue_id": issue.id,
                    "role": seat_name,
                    "type": "decision",
                    "write_rationale": "successful_turn_decision_summary",
                },
            )

        success_actions = admit_success_actions(node.success_post_actions(success_eval))
        if node.should_trigger_sandbox(success_actions):
            if self.is_sandbox_disabled():
                log_event(
                    "sandbox_trigger_skipped_policy",
                    {"run_id": run_id, "issue_id": issue.id, "seat": seat_name},
                    self.workspace_root,
                )
            else:
                await self.trigger_sandbox(epic, run_id=run_id)
            next_status = node.next_status_after_success(success_actions)
            if next_status is not None:
                await self.request_issue_transition(
                    issue=issue,
                    target_status=next_status,
                    reason="post_success_evaluator",
                    metadata={"run_id": run_id, "seat": seat_name, "turn_index": turn_index},
                    roles=roles_to_load,
                    **({"completion_request": receipt.request} if receipt is not None else {}),
                )

        await provider.clear_context()
        await self.save_checkpoint(run_id, epic, team, env, active_build)
        if self.issue_control_plane is not None:
            latest_issue = await self.async_cards.get_by_id(issue.id)
            observed_status = issue.status
            if isinstance(latest_issue, dict):
                observed_status = latest_issue.get("status", observed_status)
            elif latest_issue is not None:
                observed_status = getattr(latest_issue, "status", observed_status)
            await self.issue_control_plane.close_from_observed_status(
                session_id=run_id,
                issue_id=issue.id,
                observed_status=observed_status,
            )
