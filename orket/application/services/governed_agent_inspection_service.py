from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orket.application.services.governed_agent_replay_service import replay_governed_agent_evidence
from orket.application.services.governed_agent_scheduled_wake_service import (
    governed_agent_schedule_evaluation_view,
)
from orket.application.services.governed_agent_terminal_history import agent_terminal_history_records
from orket.application.services.governed_agent_wake_control_service import (
    governed_agent_wake_action_view,
)
from orket.application.services.governed_agent_webhook_ingress_service import (
    governed_agent_webhook_delivery_view,
)
from orket.core.contracts.governed_agent_ports import (
    GovernedAgentBrokerCallRepository,
    GovernedAgentIterationRepository,
    GovernedAgentIterationSnapshot,
)
from orket.core.contracts.governed_agent_replay import GovernedAgentReplayRepository
from orket.core.contracts.governed_agent_schedule_records import (
    GovernedAgentScheduleEvaluationRecord,
    GovernedAgentScheduleRepository,
)
from orket.core.contracts.governed_agent_wake_records import (
    GovernedAgentWakeActionRecord,
    GovernedAgentWakeControlRepository,
    GovernedAgentWakeRecord,
    GovernedAgentWakeRepository,
)
from orket.core.contracts.governed_agent_webhook_records import (
    GovernedAgentWebhookDeliveryRecord,
    GovernedAgentWebhookRepository,
)
from orket.core.contracts.pending_gate_repository import PendingGateRepository
from orket.core.contracts.repositories import ControlPlaneRecordRepository


class GovernedAgentInspectionService:
    """Read-only durable inspector and continuation replay surface."""

    def __init__(
        self,
        *,
        iteration_repository: GovernedAgentIterationRepository,
        call_repository: GovernedAgentBrokerCallRepository,
        replay_repository: GovernedAgentReplayRepository,
        wake_repository: GovernedAgentWakeRepository | None = None,
        wake_control_repository: GovernedAgentWakeControlRepository | None = None,
        schedule_repository: GovernedAgentScheduleRepository | None = None,
        webhook_repository: GovernedAgentWebhookRepository | None = None,
        record_repository: ControlPlaneRecordRepository | None = None,
        pending_gate_repository: PendingGateRepository | None = None,
    ) -> None:
        self._iterations = iteration_repository
        self._calls = call_repository
        self._replay = replay_repository
        self._wakes = wake_repository
        self._wake_controls = wake_control_repository
        self._schedules = schedule_repository
        self._webhooks = webhook_repository
        self._records = record_repository
        self._pending = pending_gate_repository

    async def inspect(self, *, run_id: str) -> dict[str, Any] | None:
        run, attempts, truth = agent_terminal_history_records(await self._replay.read_replay_evidence(run_id=run_id))
        if run is None:
            return None
        iterations = await self._iterations.list_iteration_snapshots(run_id=run_id)
        wakes = () if self._wakes is None else await self._wakes.list_wakes(target_run_id=run_id)
        effects = [] if self._records is None else await self._records.list_effect_journal_entries(run_id=run_id)
        checkpoints = await self._checkpoint_views(attempts)
        approvals = [] if self._pending is None else await self._pending.list_requests(session_id=run_id, limit=1000)
        operator_actions = await self._operator_action_views(run_id, approvals, wakes)
        iteration_views = [await self._iteration_view(snapshot) for snapshot in iterations]
        wake_actions = await self._wake_action_views(wakes)
        schedule_evaluations = await self._schedule_evaluation_views(wakes)
        webhook_deliveries = await self._webhook_delivery_views(wakes)
        return {
            "object_type": "governed_agent_inspection",
            "schema_version": "governed_agent_inspection.v1",
            "run": run.model_dump(mode="json"),
            "attempts": [attempt.model_dump(mode="json") for attempt in attempts],
            "objective_ref": None if not iterations else iterations[0].request_payload.get("objective_ref"),
            "iterations": iteration_views,
            "wakes": [_wake_view(wake) for wake in wakes],
            "wake_actions": wake_actions,
            "schedule_evaluations": schedule_evaluations,
            "webhook_deliveries": webhook_deliveries,
            "effects": [effect.model_dump(mode="json") for effect in effects],
            "approvals": [_approval_view(approval) for approval in approvals],
            "checkpoints": checkpoints,
            "operator_actions": operator_actions,
            "final_truth": None if truth is None else truth.model_dump(mode="json"),
            "operator_summary": _operator_summary(
                run=run.model_dump(mode="json"),
                iterations=iteration_views,
                wakes=wakes,
                approvals=approvals,
                effects=[effect.model_dump(mode="json") for effect in effects],
                final_truth=None if truth is None else truth.model_dump(mode="json"),
            ),
        }

    async def _wake_action_views(
        self,
        wakes: tuple[GovernedAgentWakeRecord, ...],
    ) -> list[dict[str, Any]]:
        if self._wake_controls is None:
            return []
        actions: list[GovernedAgentWakeActionRecord] = []
        for wake in wakes:
            actions.extend(await self._wake_controls.list_actions(wake_id=wake.wake_id))
        return [governed_agent_wake_action_view(action) for action in actions]

    async def _schedule_evaluation_views(
        self,
        wakes: tuple[GovernedAgentWakeRecord, ...],
    ) -> list[dict[str, Any]]:
        if self._schedules is None:
            return []
        evaluations: list[GovernedAgentScheduleEvaluationRecord] = []
        for wake in wakes:
            trigger = wake.payload.get("trigger")
            evaluation_id = trigger.get("evaluation_id") if isinstance(trigger, Mapping) else None
            if not isinstance(evaluation_id, str) or not evaluation_id.strip():
                continue
            evaluation = await self._schedules.get_evaluation(evaluation_id=evaluation_id)
            if evaluation is not None and evaluation.resulting_wake_id == wake.wake_id:
                evaluations.append(evaluation)
        return [governed_agent_schedule_evaluation_view(item) for item in evaluations]

    async def _webhook_delivery_views(
        self,
        wakes: tuple[GovernedAgentWakeRecord, ...],
    ) -> list[dict[str, Any]]:
        if self._webhooks is None:
            return []
        deliveries: list[GovernedAgentWebhookDeliveryRecord] = []
        for wake in wakes:
            trigger = wake.payload.get("trigger")
            delivery_ref = trigger.get("delivery_ref") if isinstance(trigger, Mapping) else None
            if not isinstance(delivery_ref, str) or not delivery_ref.strip():
                continue
            delivery = await self._webhooks.get_delivery(delivery_ref=delivery_ref)
            if delivery is not None and delivery.resulting_wake_id == wake.wake_id:
                deliveries.append(delivery)
        return [governed_agent_webhook_delivery_view(item) for item in deliveries]

    async def replay(self, *, run_id: str) -> dict[str, Any] | None:
        evidence = await self._replay.read_replay_evidence(run_id=run_id)
        return replay_governed_agent_evidence(run_id, evidence)

    async def _iteration_view(self, snapshot: GovernedAgentIterationSnapshot) -> dict[str, Any]:
        calls = await self._calls.list_call_records(invocation_id=snapshot.binding.invocation_id)
        return {
            "binding": {
                "run_id": snapshot.binding.run_id,
                "attempt_id": snapshot.binding.attempt_id,
                "step_id": snapshot.binding.step_id,
                "iteration_ordinal": snapshot.binding.iteration_ordinal,
                "invocation_id": snapshot.binding.invocation_id,
                "fencing_generation": snapshot.binding.fencing_generation,
                "cancellation_epoch": snapshot.binding.cancellation_epoch,
            },
            "state": snapshot.state,
            "remaining_run_budget": snapshot.request_payload["remaining_run_budget"],
            "remaining_iteration_budget": snapshot.request_payload["remaining_iteration_budget"],
            "model_profiles": snapshot.request_payload["model_profiles"],
            "context_refs": snapshot.request_payload["authoritative_context_refs"],
            "prior_verified_output_refs": snapshot.request_payload["prior_verified_output_refs"],
            "result_digest": snapshot.result_digest,
            "decision": snapshot.decision_payload,
            "uncertainty": snapshot.uncertainty,
            "model_calls": [
                {
                    "call_id": call.call_id,
                    "operation": call.operation,
                    "status": call.status,
                    "request_digest": call.request_digest,
                    "result_digest": call.result_digest,
                    "receipt": (
                        None
                        if call.result_payload is None
                        else call.result_payload.get("receipt")
                    ),
                }
                for call in calls
            ],
        }

    async def _checkpoint_views(self, attempts: list[Any]) -> list[dict[str, Any]]:
        if self._records is None:
            return []
        result: list[dict[str, Any]] = []
        for attempt in attempts:
            checkpoints = await self._records.list_checkpoints(parent_ref=attempt.attempt_id)
            for checkpoint in checkpoints:
                acceptance = await self._records.get_checkpoint_acceptance(checkpoint_id=checkpoint.checkpoint_id)
                result.append(
                    {
                        "checkpoint": checkpoint.model_dump(mode="json"),
                        "acceptance": None if acceptance is None else acceptance.model_dump(mode="json"),
                    }
                )
        return result

    async def _operator_action_views(
        self,
        run_id: str,
        approvals: list[dict[str, Any]],
        wakes: tuple[GovernedAgentWakeRecord, ...],
    ) -> list[dict[str, Any]]:
        if self._records is None:
            return []
        actions = list(await self._records.list_operator_actions(target_ref=run_id))
        for approval in approvals:
            target_ref = f"approval-request:{approval.get('request_id')}"
            actions.extend(await self._records.list_operator_actions(target_ref=target_ref))
        for wake in wakes:
            actions.extend(await self._records.list_operator_actions(target_ref=wake.wake_id))
        by_id = {action.action_id: action for action in actions}
        return [by_id[action_id].model_dump(mode="json") for action_id in sorted(by_id)]


def _wake_view(wake: GovernedAgentWakeRecord) -> dict[str, Any]:
    return {
        "wake_id": wake.wake_id,
        "source": wake.source,
        "target_kind": wake.target_kind,
        "occurrence_id": wake.occurrence_id,
        "state": wake.state,
        "claim_owner_id": wake.claim_owner_id,
        "lease_expires_at_utc": wake.lease_expires_at_utc,
        "fencing_generation": wake.fencing_generation,
        "cancellation_epoch": wake.cancellation_epoch,
        "uncertainty": wake.uncertainty,
        "result_ref": wake.result_ref,
        "last_reason": wake.last_reason,
        "trigger": _trigger_view(wake.payload.get("trigger")),
    }


def _trigger_view(value: object) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _approval_view(approval: dict[str, Any]) -> dict[str, Any]:
    return {
        key: approval.get(key)
        for key in (
            "request_id",
            "issue_id",
            "gate_mode",
            "request_type",
            "reason",
            "status",
            "payload_json",
            "resolution_json",
            "created_at",
            "resolved_at",
        )
    }


def _operator_summary(
    *,
    run: dict[str, Any],
    iterations: list[dict[str, Any]],
    wakes: tuple[GovernedAgentWakeRecord, ...],
    approvals: list[dict[str, Any]],
    effects: list[dict[str, Any]],
    final_truth: dict[str, Any] | None,
) -> dict[str, Any]:
    latest = iterations[-1] if iterations else None
    decision = None if latest is None else latest.get("decision")
    active_wake = next((wake for wake in reversed(wakes) if wake.state == "claimed"), None)
    pending = [item for item in approvals if item.get("status") == "pending"]
    capabilities = []
    if latest is not None:
        capabilities = [
            item.get("capability")
            for item in latest["remaining_iteration_budget"].get("per_capability_effects", [])
            if int(item.get("count") or 0) > 0
        ]
    lifecycle = str(run.get("lifecycle_state") or "")
    return {
        "running": active_wake is not None and lifecycle == "executing",
        "running_basis": None if active_wake is None else f"wake-claim:{active_wake.wake_id}",
        "may_continue": bool(isinstance(decision, dict) and decision.get("next_iteration_authorized")),
        "continuation_basis": None if not isinstance(decision, dict) else decision.get("rule"),
        "can_affect": sorted({str(item) for item in capabilities if item}),
        "awaits": [f"approval:{item.get('request_id')}" for item in pending]
        + (
            ["recovery"]
            if lifecycle == "recovery_pending" or any(wake.uncertainty for wake in wakes)
            else []
        ),
        "stopped_because": (
            final_truth.get("closure_basis")
            if final_truth is not None
            else None if lifecycle == "executing" else (decision or {}).get("rule", lifecycle)
        ),
        "effect_count": len(effects),
    }
