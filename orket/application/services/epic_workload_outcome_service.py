"""Own the durable handoff from workload termination to completion inspection."""
from __future__ import annotations

from typing import Any

from orket.application.services.epic_approval_recovery_service import validate_approval_recovery_artifacts
from orket.core.contracts.epic_publication import EpicPublicationRepository, EpicWorkloadOutcome


class EpicWorkloadOutcomeService:
    def __init__(self, repository: EpicPublicationRepository, ledger: Any):
        self.repository, self.ledger = repository, ledger

    async def retain(self, outcome: EpicWorkloadOutcome) -> EpicWorkloadOutcome:
        captured = EpicWorkloadOutcome.model_validate_json(outcome.model_dump_json())
        async with self.repository.transaction(captured.session_id) as transaction:
            await validate_approval_recovery_artifacts(transaction, captured.artifacts)
            await transaction.save_outcome(captured)
            if await transaction.get_outcome() != captured:
                raise ValueError("E_EPIC_WORKLOAD_OUTCOME_UNCONFIRMED")
        return captured

    async def read(self, session_id: str, request: dict[str, Any],
                   export_binding: dict[str, Any]) -> EpicWorkloadOutcome | None:
        async with self.repository.transaction(session_id) as transaction:
            outcome = await transaction.get_outcome()
            if outcome is not None:
                await validate_approval_recovery_artifacts(transaction, outcome.artifacts)
            if outcome is not None and (outcome.request != request or outcome.export_binding != export_binding):
                raise ValueError("E_EPIC_WORKLOAD_OUTCOME_REQUEST_CONFLICT")
            if outcome is not None and await transaction.get_preparation() is None and await transaction.get() is None:
                row = await self.ledger.get_run(session_id)
                if row is None or row.get("status") != "running":
                    raise ValueError("E_EPIC_WORKLOAD_OUTCOME_RUN_MISSING")
                original_run = outcome.artifacts["control_plane_run_record"]
                if row.get("artifact_json", {}).get("control_plane_run_record") != original_run:
                    raise ValueError("E_EPIC_WORKLOAD_OUTCOME_RUN_CONFLICT")
        return outcome
