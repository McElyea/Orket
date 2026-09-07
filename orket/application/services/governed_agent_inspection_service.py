from __future__ import annotations

from typing import Any

from orket.application.services.governed_agent_iteration_policy import agent_payload_digest
from orket.application.services.governed_agent_loop_service import GovernedAgentFinalTruthRepository
from orket.application.services.governed_agent_ports import (
    GovernedAgentBrokerCallRepository,
    GovernedAgentIterationRepository,
    GovernedAgentIterationSnapshot,
)
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)


class GovernedAgentInspectionService:
    """Read-only durable inspector and continuation replay surface."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        iteration_repository: GovernedAgentIterationRepository,
        call_repository: GovernedAgentBrokerCallRepository,
        truth_repository: GovernedAgentFinalTruthRepository,
    ) -> None:
        self._execution = execution_repository
        self._iterations = iteration_repository
        self._calls = call_repository
        self._truth = truth_repository

    async def inspect(self, *, run_id: str) -> dict[str, Any] | None:
        run = await self._execution.get_run_record(run_id=run_id)
        if run is None:
            return None
        attempts = await self._execution.list_attempt_records(run_id=run_id)
        iterations = await self._iterations.list_iteration_snapshots(run_id=run_id)
        truth = await self._truth.get_final_truth(run_id=run_id)
        return {
            "object_type": "governed_agent_inspection",
            "schema_version": "governed_agent_inspection.v1",
            "run": run.model_dump(mode="json"),
            "attempts": [attempt.model_dump(mode="json") for attempt in attempts],
            "iterations": [await self._iteration_view(snapshot) for snapshot in iterations],
            "final_truth": None if truth is None else truth.model_dump(mode="json"),
        }

    async def replay(self, *, run_id: str) -> dict[str, Any] | None:
        snapshots = await self._iterations.list_iteration_snapshots(run_id=run_id)
        if not snapshots and await self._execution.get_run_record(run_id=run_id) is None:
            return None
        replays = [_replay_snapshot(snapshot) for snapshot in snapshots]
        return {
            "object_type": "governed_agent_replay",
            "schema_version": "governed_agent_replay.v1",
            "run_id": run_id,
            "status": "matched" if all(item["matched"] for item in replays) else "mismatch",
            "decisions": replays,
        }

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


def _replay_snapshot(snapshot: GovernedAgentIterationSnapshot) -> dict[str, Any]:
    if snapshot.decision_inputs is None or snapshot.decision_payload is None:
        return {
            "invocation_id": snapshot.binding.invocation_id,
            "matched": False,
            "reason": "decision_not_published",
        }
    replayed = decide_governed_agent_continuation(
        GovernedAgentContinuationInputs(**snapshot.decision_inputs)
    ).to_payload()
    replayed_digest = agent_payload_digest(replayed)
    return {
        "invocation_id": snapshot.binding.invocation_id,
        "matched": replayed == snapshot.decision_payload and replayed_digest == snapshot.decision_digest,
        "recorded_decision_digest": snapshot.decision_digest,
        "replayed_decision_digest": replayed_digest,
        "rule": replayed["rule"],
        "disposition": replayed["disposition"],
    }
