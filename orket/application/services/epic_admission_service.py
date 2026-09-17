"""Reserve shared standard-epic resources before initialization or dispatch."""
from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from orket.core.contracts.epic_publication import (
    EpicAdmissionRecovery,
    EpicAdmissionRecoveryRequest,
    EpicPublicationPlan,
    EpicPublicationRepository,
    EpicPublicationTransaction,
    EpicRunAdmission,
    admission_recovery_action,
)


class EpicAdmissionService:
    def __init__(self, repository: EpicPublicationRepository, *, owner_id: Callable[[], str], now: Callable[[], str]):
        self.repository, self.owner_id, self.now = repository, owner_id, now

    async def claim(self, session_id: str, request: dict[str, Any], export_binding: dict[str, Any]) -> EpicRunAdmission:
        workspace = await asyncio.to_thread(Path(request["scope"]["workspace"]).resolve)
        resources = sorted({"workspace:" + os.path.normcase(str(workspace)), "build:" + request["build_id"],
                            *("card:" + issue["id"] for issue in request["epic"]["issues"])})
        record = EpicRunAdmission(session_id=session_id, owner_id=self.owner_id(), request=request,
                                  export_binding=export_binding, resources=resources, admitted_at=self.now())
        record = EpicRunAdmission.model_validate_json(record.model_dump_json())
        async with self.repository.transaction(session_id) as transaction:
            prior = await transaction.get_admission()
            if prior is not None:
                if prior.request != request or prior.export_binding != export_binding:
                    raise ValueError("E_EPIC_ADMISSION_REQUEST_CONFLICT")
                raise ValueError("E_EPIC_ADMISSION_OUTCOME_UNCERTAIN")
            conflicts = await transaction.admission_conflicts(resources)
            if conflicts:
                raise ValueError("E_EPIC_ADMISSION_RESOURCE_BUSY:" + ",".join(sorted(conflicts)))
            await transaction.save_admission(record)
            if await transaction.get_admission() != record:
                raise ValueError("E_EPIC_ADMISSION_UNCONFIRMED")
        return record

    async def recover_claim(self, session_id: str, request: dict[str, Any], export_binding: dict[str, Any],
                            recovery: EpicAdmissionRecoveryRequest) -> EpicRunAdmission:
        async with self.repository.transaction(session_id) as transaction:
            prior = await transaction.get_admission()
            if (prior is None or recovery.session_id != session_id or prior.request != request
                    or prior.export_binding != export_binding):
                raise ValueError("E_EPIC_ADMISSION_RECOVERY_REQUEST_CONFLICT")
            matches = [entry for entry in prior.recoveries if entry.request.request_id == recovery.request_id]
            if matches:
                if matches[0].request != recovery:
                    raise ValueError("E_EPIC_ADMISSION_RECOVERY_REQUEST_CONFLICT")
                if matches[0] != prior.recoveries[-1]:
                    raise ValueError("E_EPIC_ADMISSION_RECOVERY_SUPERSEDED")
                return prior
            if prior.phase != "active" or prior.initialization_started:
                raise ValueError("E_EPIC_ADMISSION_RECOVERY_REQUIRES_PRE_INITIALIZATION")
            if (prior.owner_id != recovery.expected_owner_id or prior.fencing_generation != recovery.expected_fencing_generation
                    or prior.claim_ref()["digest"] != recovery.expected_claim_digest):
                raise ValueError("E_EPIC_ADMISSION_FENCE_CONFLICT")
            if await transaction.get_outcome() or await transaction.get_preparation() or await transaction.get():
                raise ValueError("E_EPIC_ADMISSION_RECOVERY_EFFECT_EVIDENCE")
            owner, at = self.owner_id(), self.now()
            entry = EpicAdmissionRecovery(request=recovery, owner_id=owner, decided_at=at,
                                           action=admission_recovery_action(recovery, owner, at))
            replacement = prior.model_copy(update={"owner_id": owner, "fencing_generation": prior.fencing_generation + 1,
                                                   "recoveries": (*prior.recoveries, entry)})
            replacement = EpicRunAdmission.model_validate_json(replacement.model_dump_json())
            await transaction.save_admission(replacement)
            if await transaction.get_admission() != replacement:
                raise ValueError("E_EPIC_ADMISSION_RECOVERY_UNCONFIRMED")
            return replacement

    async def begin_initialization(self, admission: EpicRunAdmission) -> EpicRunAdmission:
        async with self.repository.transaction(admission.session_id) as transaction:
            retained = await transaction.get_admission()
            if retained != admission or retained.phase != "active":
                raise ValueError("E_EPIC_ADMISSION_FENCE_CONFLICT")
            if retained.initialization_started:
                raise ValueError("E_EPIC_ADMISSION_INITIALIZATION_UNCERTAIN")
            started = retained.model_copy(update={"initialization_started": True})
            await transaction.save_admission(started)
            if await transaction.get_admission() != started:
                raise ValueError("E_EPIC_ADMISSION_INITIALIZATION_UNCONFIRMED")
            return started

    @staticmethod
    async def validate(transaction: EpicPublicationTransaction, plan: EpicPublicationPlan) -> EpicRunAdmission | None:
        expected = plan.ledger["artifacts"].get("epic_run_admission")
        record = await transaction.get_admission()
        if expected is None and record is None:
            return None  # Retained publication predating admission is not backfilled.
        if record is None or not record.initialization_started or record.claim_ref() != expected or record.request != plan.request:
            raise ValueError("E_EPIC_ADMISSION_EVIDENCE_CONFLICT")
        publication = await transaction.get()
        if record.phase == "released" and (publication is None or publication.phase != 4):
            raise ValueError("E_EPIC_ADMISSION_RELEASE_UNCONFIRMED")
        return record

    @staticmethod
    async def release_verified(transaction: EpicPublicationTransaction, plan: EpicPublicationPlan) -> None:
        record = await EpicAdmissionService.validate(transaction, plan)
        if record is None:
            return
        released = record.model_copy(update={"phase": "released"})
        await transaction.save_admission(released)
        if await transaction.get_admission() != released:
            raise ValueError("E_EPIC_ADMISSION_RELEASE_UNCONFIRMED")
