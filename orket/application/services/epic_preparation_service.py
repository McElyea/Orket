"""Retain closeout inputs and fence initial or explicitly recovered export."""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from orket.application.services.epic_export_recovery_service import (
    EXPORT_OWNER_ARTIFACT,
    EpicExportRecoveryService,
    retained_export_owner,
)
from orket.application.services.epic_publication_service import EpicPublicationService
from orket.core.contracts.epic_export_recovery import EpicExportDispatch, EpicExportRecoveryRequest
from orket.core.contracts.epic_publication import (
    EpicPreparationRecord,
    EpicPublicationPlan,
    EpicPublicationRecord,
    EpicPublicationTransaction,
)
from orket.core.contracts.gitea_export import GiteaExportIntent
from orket.exceptions import OrketInfrastructureError


class EpicPreparationService:
    def __init__(self, *, publication: EpicPublicationService, materialize_receipts: Callable[..., Awaitable[Any]],
                 materialize_summary: Callable[..., Awaitable[Any]], export_artifacts: Callable[..., Awaitable[Any]],
                 export_binding: dict[str, Any], now: Callable[[], str], owner_id: Callable[[], str],
                 prepare_export: Callable[..., Awaitable[Any]], reconcile_export: Callable[..., Awaitable[Any]]):
        self.prepare_export, self.reconcile_export = prepare_export, reconcile_export
        self.publication = publication
        self.repository = publication.repository
        self.materialize_receipts, self.materialize_summary = materialize_receipts, materialize_summary
        self.export_artifacts, self.export_binding, self.now = export_artifacts, dict(export_binding), now
        self.export_recovery = EpicExportRecoveryService(owner_id=owner_id, now=now)

    async def prepare(self, plan: EpicPublicationPlan, *, policy: dict[str, Any]) -> EpicPublicationPlan:
        record = EpicPreparationRecord(plan=plan, policy=policy, export_binding=self.export_binding,
                                       artifacts=plan.ledger["artifacts"])
        record = EpicPreparationRecord.model_validate_json(record.model_dump_json())
        async with self.repository.transaction(plan.session_id) as transaction:
            prior = await transaction.get_preparation()
            if prior is None:
                await transaction.save_preparation(record)
            elif prior.plan != record.plan or prior.policy != policy or prior.export_binding != self.export_binding:
                raise ValueError("E_EPIC_PREPARATION_CONFLICT")
        return await self._finish(plan.session_id, plan.request)

    async def recover(self, session_id: str, request: dict[str, Any]) -> None:
        async with self.repository.transaction(session_id) as transaction:
            record = await transaction.get_preparation()
        if record is not None:
            await self._finish(session_id, request)

    async def recover_export(self, session_id: str, request: dict[str, Any], recovery: EpicExportRecoveryRequest) -> None:
        async with self.repository.transaction(session_id) as transaction:
            record = await transaction.get_preparation()
            if (record is None or record.plan.request != request or record.export_binding != self.export_binding
                    or not record.export_binding["enabled"]):
                raise ValueError("E_EPIC_EXPORT_RECOVERY_REQUEST_CONFLICT")
            await self.publication.validate_acceptance(record.plan, transaction=transaction, require_closeout=False)
            owner = await self.export_recovery.replace(transaction, record, recovery)
        await self._finish(session_id, request, export_owner=owner, confirm_first=True)

    async def _finish(self, session_id: str, request: dict[str, Any], *,
                      export_owner: EpicExportDispatch | None = None, confirm_first: bool = False) -> EpicPublicationPlan:
        while True:
            async with self.repository.transaction(session_id) as transaction:
                record = await transaction.get_preparation()
                if record is None or record.plan.request != request or record.export_binding != self.export_binding:
                    raise ValueError("E_EPIC_PREPARATION_REQUEST_CONFLICT")
                await self.publication.validate_acceptance(record.plan, transaction=transaction, require_closeout=False)
                current_owner = await retained_export_owner(transaction, record)
                if record.phase == 5:
                    retained = await transaction.get()
                    if retained is None:
                        raise ValueError("E_EPIC_PUBLICATION_RECOVERY_EVIDENCE_MISSING")
                    return retained.plan
                if export_owner is not None and current_owner != export_owner:
                    raise ValueError("E_EPIC_EXPORT_FENCE_CONFLICT")
                if record.phase == 4 and (export_owner is None or confirm_first):
                    if record.export_intent is None:
                        raise ValueError("E_EPIC_EXPORT_OUTCOME_UNCERTAIN")
                    exported = await self._invoke("reconcile export", self.reconcile_export,
                                                  export_intent=record.export_intent)
                    if exported:
                        return await self._promote(record, transaction, exported)
                    if export_owner is None:
                        raise ValueError("E_EPIC_EXPORT_OUTCOME_UNCERTAIN")
                if record.phase == 3 and record.export_binding["enabled"]:
                    intent = await self._invoke("prepare export", self.prepare_export, **self._export_arguments(record))
                    if intent is None:
                        raise ValueError("E_EPIC_EXPORT_INTENT_MISSING")
                    intent = GiteaExportIntent.model_validate(intent)
                    if intent.run_id != session_id or intent.binding != self.export_binding:
                        raise ValueError("E_EPIC_EXPORT_INTENT_CONFLICT")
                    record = record.model_copy(update={"phase": 4, "export_intent": intent})
                    export_owner = await self.export_recovery.claim(transaction, record)
                    record = record.model_copy(update={"artifacts": {
                        **record.artifacts, EXPORT_OWNER_ARTIFACT: export_owner.origin_ref()}})
                    await transaction.save_preparation(record)
                    continue
                if record.phase in (3, 4):
                    return await self._export_and_promote(record, transaction)
                steps = (self._closeout, self._receipts, self._summary)
                updated = await steps[record.phase](record)
                await transaction.save_preparation(updated.model_copy(update={"phase": record.phase + 1}))

    async def _closeout(self, record: EpicPreparationRecord) -> EpicPreparationRecord:
        ledger = record.plan.ledger
        run, attempt = await self.publication.control_plane.finalize_execution(
            run_id=record.artifacts["control_plane_run_record"]["run_id"],
            session_status=ledger["status"], failure_reason=ledger.get("failure_reason"))
        artifacts = {**record.artifacts, "control_plane_run_record": run.model_dump(mode="json"),
                     "control_plane_attempt_record": attempt.model_dump(mode="json")}
        return record.model_copy(update={"artifacts": artifacts})

    async def _receipts(self, record: EpicPreparationRecord) -> EpicPreparationRecord:
        projection = await self._invoke("materialize protocol receipts", self.materialize_receipts,
                                        run_id=record.plan.session_id)
        artifacts = {**record.artifacts, **({"protocol_receipts": projection} if projection else {})}
        return record.model_copy(update={"artifacts": artifacts})

    async def _summary(self, record: EpicPreparationRecord) -> EpicPreparationRecord:
        ledger = record.plan.ledger
        summary, artifacts = await self._invoke(
            "materialize run summary", self.materialize_summary, run_id=record.plan.session_id,
            session_status=ledger["status"], failure_reason=ledger.get("failure_reason"),
            artifacts=record.model_copy(deep=True).artifacts, finalized_at=ledger["finalized_at"],
            phase_c_truth_policy=record.policy)
        return record.model_copy(update={"summary": summary, "artifacts": artifacts})

    async def _export_and_promote(self, record: EpicPreparationRecord,
                                  transaction: EpicPublicationTransaction) -> EpicPublicationPlan:
        exported = await self._invoke("export run artifacts", self.export_artifacts,
                                      export_intent=record.export_intent, **self._export_arguments(record))
        if record.export_binding["enabled"] and not exported:
            raise ValueError("E_EPIC_EXPORT_RECEIPT_MISSING")
        return await self._promote(record, transaction, exported)

    async def _promote(self, record: EpicPreparationRecord, transaction: EpicPublicationTransaction,
                       exported: dict[str, Any] | None) -> EpicPublicationPlan:
        ledger = record.plan.ledger
        artifacts = {**record.artifacts, **({"gitea_export": exported} if exported else {})}
        owner = await retained_export_owner(transaction, record)
        if owner is not None:
            if (not exported or record.export_intent is None or exported.get("commit") != record.export_intent.commit
                    or exported.get("tree") != record.export_intent.tree):
                raise ValueError("E_EPIC_EXPORT_PUBLICATION_RECEIPT_CONFLICT")
            await transaction.export_dispatch.save(owner.model_copy(update={"phase": "settled"}))
            artifacts[EXPORT_OWNER_ARTIFACT] = owner.claim_ref()
        prepared = record.plan.model_copy(update={"ledger": {**ledger, "artifacts": artifacts,
                                               "summary": record.summary, "finalized_at": self.now()}})
        if record.phase == 3:
            record = record.model_copy(update={"phase": 4})
            await transaction.save_preparation(record)
        await transaction.save(EpicPublicationRecord(plan=prepared))
        await transaction.save_preparation(record.model_copy(update={"phase": 5}))
        return prepared

    @staticmethod
    def _export_arguments(record: EpicPreparationRecord) -> dict[str, Any]:
        ledger = record.plan.ledger
        return {"run_id": record.plan.session_id, "run_type": "epic", "run_name": record.plan.request["epic"]["name"],
                "build_id": record.plan.request["build_id"], "session_status": ledger["status"], "summary": record.summary,
                "failure_reason": ledger.get("failure_reason"), "failure_class": ledger.get("failure_class"),
                "export_day": ledger["finalized_at"].split("T", 1)[0], "export_time": ledger["finalized_at"]}

    @staticmethod
    async def _invoke(operation: str, callback: Callable[..., Awaitable[Any]], **kwargs: Any) -> Any:
        try:
            return await callback(**kwargs)
        except (RuntimeError, OSError, TimeoutError) as exc:
            raise OrketInfrastructureError(f"{operation}: {exc}") from exc
