"""Finish retained epic publication without executing work or resetting cards."""
from __future__ import annotations

import asyncio
import json
from functools import partial
from pathlib import Path
from typing import Any

from orket.application.services.card_completion_outcome_service import inspect_build_completion
from orket.application.services.epic_admission_service import EpicAdmissionService
from orket.application.services.epic_approval_recovery_service import validate_approval_recovery_artifacts
from orket.application.services.epic_export_recovery_service import validate_published_export
from orket.application.services.runtime_execution_result_service import published_execution_result
from orket.core.contracts.epic_publication import (
    EpicPublicationPlan,
    EpicPublicationRecord,
    EpicPublicationRepository,
    EpicPublicationTransaction,
)
from orket.core.contracts.repositories import CardRepository
from orket.core.contracts.runtime_execution_result import RuntimeExecutionResult
from orket.core.domain import RunState
from orket.logging import log_event


class EpicPublicationService:
    def __init__(self, *, repository: EpicPublicationRepository, cards: CardRepository, sessions: Any,
                 snapshots: Any, success: Any, ledger: Any, control_plane: Any, scope: dict[str, Any], storage_binding=None):
        self.repository, self.cards, self.sessions = repository, cards, sessions
        self.snapshots, self.success, self.ledger = snapshots, success, ledger
        self.control_plane, self.scope = control_plane, scope
        self.storage_binding = storage_binding

    def request_scope(self, session_id: str) -> dict[str, Any]:
        if self.storage_binding is not None:
            return self.storage_binding.request_scope(session_id, self.scope)
        return dict(self.scope)

    async def recover(self, session_id: str, request: dict[str, Any]) -> RuntimeExecutionResult | None:
        snapshots = self.snapshots
        async with self.repository.transaction(session_id) as transaction:
            record = await transaction.get()
        if record is None:
            await self._require_no_unrecoverable_closeout(session_id)
            return None
        if record.plan.request != request:
            raise ValueError("E_EPIC_PUBLICATION_REQUEST_CONFLICT")
        return await self._finish(record.plan, snapshots)

    async def publish(self, plan: EpicPublicationPlan) -> RuntimeExecutionResult:
        snapshots = self.snapshots
        # Freeze nested JSON inputs before any repository or caller can mutate them.
        plan = EpicPublicationPlan.model_validate_json(plan.model_dump_json())
        async with self.repository.transaction(plan.session_id) as transaction:
            existing = await transaction.get()
            if existing is None:
                await transaction.save(EpicPublicationRecord(plan=plan))
            elif existing.plan != plan:
                raise ValueError("E_EPIC_PUBLICATION_CONFLICT")
        return await self._finish(plan, snapshots)

    async def _require_no_unrecoverable_closeout(self, session_id: str) -> None:
        async with self.repository.transaction(session_id) as transaction:
            if await transaction.get() is not None or await transaction.get_preparation() is not None:
                return
            row = await self.ledger.get_run(session_id)
            if row is None:
                return
            artifacts = row.get("artifact_json")
            retained = artifacts.get("control_plane_run_record") if isinstance(artifacts, dict) else None
            if isinstance(retained, dict) and retained.get("run_id"):
                run = await self.control_plane.execution_repository.get_run_record(run_id=retained["run_id"])
                if run is not None and run.lifecycle_state != RunState.EXECUTING:
                    raise ValueError("E_EPIC_PUBLICATION_RECOVERY_EVIDENCE_MISSING")
            if row.get("status") != "running":
                raise ValueError("E_EPIC_PUBLICATION_RECOVERY_EVIDENCE_MISSING")
            outcome = await transaction.get_outcome()
            if outcome is None and await transaction.approval_pauses.latest() is None:
                raise ValueError("E_EPIC_WORKLOAD_OUTCOME_UNCERTAIN")

    async def _finish(self, plan: EpicPublicationPlan, snapshots: Any) -> RuntimeExecutionResult:
        while True:
            async with self.repository.transaction(plan.session_id) as transaction:
                record = await transaction.get()
                if record is None or record.plan != plan:
                    raise ValueError("E_EPIC_PUBLICATION_CONFLICT")
                await self.validate_acceptance(plan, transaction=transaction)
                if record.phase == 4:
                    await self._verify_published(plan, snapshots)
                    result = await published_execution_result(self, plan, record)
                    await EpicAdmissionService.release_verified(transaction, plan)
                    return result
                operations = (self._publish_ledger, self._publish_session,
                              partial(self._publish_snapshot, snapshots=snapshots),
                              partial(self._publish_success, snapshots=snapshots))
                await operations[record.phase](plan)
                await transaction.save(record.model_copy(update={"phase": record.phase + 1}))

    async def validate_acceptance(self, plan: EpicPublicationPlan, *, transaction: EpicPublicationTransaction,
                                  require_closeout: bool = True) -> None:
        await EpicAdmissionService.validate(transaction, plan)
        await validate_approval_recovery_artifacts(transaction, plan.ledger["artifacts"])
        if require_closeout:
            await validate_published_export(transaction, plan)
        expected = plan.ledger["artifacts"].get("card_completion_outcome")
        if expected is not None:
            observed = await inspect_build_completion(cards=self.cards, build_id=expected["build_id"],
                                                      expected_card_ids=tuple(expected["expected_card_ids"]))
            if observed.to_artifact() != expected:
                raise ValueError("E_EPIC_PUBLICATION_ACCEPTANCE_CHANGED")
        if not require_closeout:
            return
        await self.control_plane.finalize_execution(
            run_id=plan.ledger["artifacts"]["control_plane_run_record"]["run_id"],
            session_status=plan.ledger["status"], failure_reason=plan.ledger.get("failure_reason"))

    async def _publish_ledger(self, plan: EpicPublicationPlan) -> None:
        row = await self.ledger.get_run(plan.session_id)
        if row is None:
            raise ValueError("E_EPIC_PUBLICATION_RUN_MISSING")
        if not self._ledger_matches(plan, row):
            if row.get("status") != "running":
                raise ValueError("E_EPIC_PUBLICATION_RUN_CONFLICT")
            await self.ledger.finalize_run(**plan.ledger)
        if not self._ledger_matches(plan, await self.ledger.get_run(plan.session_id)):
            raise ValueError("E_EPIC_PUBLICATION_RUN_UNCONFIRMED")

    async def _publish_session(self, plan: EpicPublicationPlan) -> None:
        row = await self.sessions.get_session(plan.session_id)
        if row is None:
            raise ValueError("E_EPIC_PUBLICATION_SESSION_MISSING")
        if not self._session_matches(plan, row):
            if row.get("status") not in ("Started", "running", plan.ledger["status"]):
                raise ValueError("E_EPIC_PUBLICATION_SESSION_CONFLICT")
            await self.sessions.complete_session(plan.session_id, plan.ledger["status"], plan.transcript)
        if not self._session_matches(plan, await self.sessions.get_session(plan.session_id)):
            raise ValueError("E_EPIC_PUBLICATION_SESSION_UNCONFIRMED")
        payload = {"run_id": plan.session_id, "status": plan.ledger["status"]}
        payload.update({key: plan.ledger[key] for key in ("failure_reason", "failure_class") if plan.ledger.get(key) is not None})
        await asyncio.to_thread(log_event, "session_end", payload, workspace=Path(self.scope["workspace"]))

    async def _publish_snapshot(self, plan: EpicPublicationPlan, snapshots: Any) -> None:
        if plan.snapshot is None:
            return
        if not self._snapshot_matches(plan, await snapshots.get(plan.session_id)):
            await snapshots.record(plan.session_id, plan.snapshot, plan.transcript)
        if not self._snapshot_matches(plan, await snapshots.get(plan.session_id)):
            raise ValueError("E_EPIC_PUBLICATION_SNAPSHOT_UNCONFIRMED")

    async def _publish_success(self, plan: EpicPublicationPlan, snapshots: Any) -> None:
        if plan.ledger["status"] != "done":
            return
        expected = self._success_payload(plan)
        row = await self.success.get(plan.session_id)
        if row is not None and not all(row.get(key) == value for key, value in expected.items()):
            raise ValueError("E_EPIC_PUBLICATION_SUCCESS_CONFLICT")
        if row is None:
            await self.success.record_success(**expected)
        row = await self.success.get(plan.session_id)
        if row is None or not all(row.get(key) == value for key, value in expected.items()):
            raise ValueError("E_EPIC_PUBLICATION_SUCCESS_UNCONFIRMED")
        await asyncio.to_thread(log_event, "success_recorded", {"run_id": plan.session_id, "type": "EPIC_COMPLETED"},
                                workspace=Path(self.scope["workspace"]))
        await self._verify_published(plan, snapshots)
        await asyncio.to_thread(log_event, "orchestrator_epic_complete",
                                {"run_id": plan.session_id, "epic": plan.snapshot["epic"]["name"]},
                                workspace=Path(self.scope["workspace"]))

    async def _verify_published(self, plan: EpicPublicationPlan, snapshots: Any) -> None:
        checks = [self._ledger_matches(plan, await self.ledger.get_run(plan.session_id)),
                  self._session_matches(plan, await self.sessions.get_session(plan.session_id))]
        if plan.snapshot is not None:
            checks.append(self._snapshot_matches(plan, await snapshots.get(plan.session_id)))
        if plan.ledger["status"] == "done":
            success = await self.success.get(plan.session_id)
            checks.append(success is not None and all(success.get(k) == v for k, v in self._success_payload(plan).items()))
        if not all(checks):
            raise ValueError("E_EPIC_PUBLICATION_RETAINED_EFFECT_MISSING")

    @staticmethod
    def _ledger_matches(plan: EpicPublicationPlan, row: dict[str, Any] | None) -> bool:
        if row is None or row.get("status") != plan.ledger["status"]:
            return False
        for key in ("failure_class", "failure_reason"):
            if row.get(key) != plan.ledger.get(key):
                return False
        return all(isinstance(row.get(target), dict) and all(row[target].get(k) == v for k, v in plan.ledger[source].items())
                   for source, target in (("summary", "summary_json"), ("artifacts", "artifact_json")))

    @staticmethod
    def _session_matches(plan: EpicPublicationPlan, row: dict[str, Any] | None) -> bool:
        return bool(row and row.get("status") == plan.ledger["status"]
                    and json.loads(row.get("transcript") or "null") == plan.transcript)

    @staticmethod
    def _snapshot_matches(plan: EpicPublicationPlan, row: dict[str, Any] | None) -> bool:
        return bool(row and json.loads(row["config_json"]) == plan.snapshot
                    and json.loads(row["log_history"]) == plan.transcript)

    @staticmethod
    def _success_payload(plan: EpicPublicationPlan) -> dict[str, Any]:
        return {"session_id": plan.session_id, "success_type": "EPIC_COMPLETED",
                "artifact_ref": f"build:{plan.snapshot['build_id']}", "human_ack": None}
