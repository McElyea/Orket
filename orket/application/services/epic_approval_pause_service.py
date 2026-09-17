"""Retain unfinished epic execution and consume resolved approval pauses once."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

from orket.application.services.epic_approval_recovery_service import (
    inspect_approval_recovery,
    retain_approval_recovery,
    validate_approval_recovery_artifacts,
)
from orket.application.services.governed_turn_tool_approval_continuation_service import (
    ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS,
    read_approval_execution,
    stop_approval_execution,
)
from orket.application.services.turn_tool_control_plane_support import run_id_for
from orket.application.workflows.epic_approval_checkpoint import validate_approval_checkpoints
from orket.core.contracts.epic_approval_pause import EpicApprovalPause
from orket.core.contracts.epic_approval_recovery import (
    EPIC_APPROVAL_RECOVERY_ARTIFACT,
    EPIC_CONTINUATION_LOCK_ARTIFACT,
    EpicContinuationLockRef,
)
from orket.core.contracts.epic_publication import EpicPublicationRepository
from orket.core.domain import AttemptState, RunState
from orket.exceptions import ApprovalPending


def approval_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in ("session_id", "issue_id", "seat_name", "gate_mode", "request_type",
                                    "reason", "payload_json")}


class EpicApprovalPauseService:
    def __init__(self, *, repository: EpicPublicationRepository, pending_gates: Any, ledger: Any,
                 execution_repository: Any, publication: Any, transactions: Any, locks: Any, artifact_writer: Any, now: Any):
        self.repository, self.pending_gates, self.ledger = repository, pending_gates, ledger
        self.execution_repository, self.publication = execution_repository, publication
        self.transactions = transactions
        self.locks, self.artifact_writer, self.now = locks, artifact_writer, now

    async def _requests(self, session_id: str) -> dict[str, dict[str, Any]]:
        rows = await self.pending_gates.list_requests(session_id=session_id, limit=1001)
        if len(rows) > 1000:
            raise ValueError("E_EPIC_APPROVAL_INVENTORY_INCOMPLETE")
        return {row["request_id"]: row for row in rows if row["request_type"] == "tool_approval"}

    @staticmethod
    def _validate_identity(session_id: str, identity: dict[str, Any]) -> None:
        payload = identity["payload_json"]
        tool = payload.get("tool")
        turn = payload.get("turn_index")
        if (identity["session_id"] != session_id or identity["gate_mode"] != "approval_required"
                or identity["request_type"] != "tool_approval"
                or tool not in ADMITTED_GOVERNED_TURN_TOOL_APPROVAL_CONTINUATION_TOOLS
                or identity["reason"] != f"approval_required_tool:{tool}" or type(turn) is not int or turn < 1
                or payload.get("control_plane_target_ref") != run_id_for(
                    session_id=session_id, issue_id=identity["issue_id"], role_name=identity["seat_name"], turn_index=turn)):
            raise ValueError("E_EPIC_APPROVAL_IDENTITY_CONFLICT")

    async def retain(self, *, session_id: str, request: dict[str, Any], export_binding: dict[str, Any],
                     epic_asset: str, model_override: str,
                     artifacts: dict[str, Any], transcript: list[dict[str, Any]]) -> EpicApprovalPause:
        rows = await self._requests(session_id)
        identities = {key: approval_identity(row) for key, row in rows.items()}
        for identity in identities.values():
            self._validate_identity(session_id, identity)
        async with self.repository.transaction(session_id) as tx:
            prior = await tx.approval_pauses.latest()
            await validate_approval_recovery_artifacts(tx, artifacts)
            record = EpicApprovalPause(session_id=session_id, sequence=prior.sequence + 1 if prior else 1,
                                       epic_asset=epic_asset, model_override=model_override,
                                       request=request, export_binding=export_binding, artifacts=artifacts,
                                       transcript=transcript, approvals=identities)
            record = EpicApprovalPause.model_validate_json(record.model_dump_json())
            await self._validate_execution(tx, record)
            await tx.approval_pauses.save(record)
            if await tx.approval_pauses.latest() != record:
                raise ValueError("E_EPIC_APPROVAL_PAUSE_UNCONFIRMED")
        return record

    async def request_for(self, session_id: str, approval_id: str, *, allow_absent: bool = False) -> EpicApprovalPause | None:
        async with self.repository.transaction(session_id) as tx:
            pause = await tx.approval_pauses.latest()
            if pause is None and allow_absent:
                return None
            if pause is None or approval_id not in pause.approvals:
                raise ValueError("E_EPIC_APPROVAL_PAUSE_MISSING")
            return pause

    @asynccontextmanager
    async def continuation(self, session_id, request, export_binding, recovery=None):
        async with self.repository.transaction(session_id) as tx:
            observed = await tx.approval_pauses.latest()
        if observed is None:
            if recovery is not None:
                raise ValueError("E_EPIC_APPROVAL_RECOVERY_PAUSE_CONFLICT")
            yield None
            return
        marker = observed.artifacts.get(EPIC_CONTINUATION_LOCK_ARTIFACT)
        expected = EpicContinuationLockRef.model_validate(marker) if marker is not None else None
        async with self.locks.hold(session_id, expected=expected) as lock:
            claimed = await self._claim(session_id, request, export_binding, lock, recovery)
            yield claimed

    async def observe_recovery(self, session_id, request, export_binding, recovery):
        async with self.repository.transaction(session_id) as tx:
            _, _, _, observed = await inspect_approval_recovery(tx, recovery, request, export_binding)
            return observed

    async def recovery_artifacts(self, session_id):
        async with self.repository.transaction(session_id) as tx:
            records = await tx.approval_pauses.recoveries()
            return {EPIC_APPROVAL_RECOVERY_ARTIFACT: [record.reference() for record in records]} if records else {}

    async def _claim(self, session_id: str, request: dict[str, Any],
                     export_binding: dict[str, Any], lock, recovery) -> EpicApprovalPause | None:
        async with self.repository.transaction(session_id) as tx:
            record = await tx.approval_pauses.latest()
            if record is None:
                raise ValueError("E_EPIC_APPROVAL_PAUSE_MISSING")
            if record.request != request or record.export_binding != export_binding:
                raise ValueError("E_EPIC_APPROVAL_REQUEST_CONFLICT")
            await self._validate_execution(tx, record)
            if recovery is not None:
                return await self._recover_claim(tx, record, request, export_binding, lock, recovery)
            if record.phase != "waiting":
                raise ValueError("E_EPIC_APPROVAL_CONTINUATION_UNCERTAIN")
            decisions = await self._resolved_decisions(record)
            artifacts = {**record.artifacts, EPIC_CONTINUATION_LOCK_ARTIFACT: lock.model_dump(mode="json")}
            claimed = record.model_copy(update={"phase": "claimed", "decisions": decisions, "artifacts": artifacts})
            await tx.approval_pauses.save(claimed)
            if await tx.approval_pauses.latest() != claimed:
                raise ValueError("E_EPIC_APPROVAL_CLAIM_UNCONFIRMED")
            return claimed

    async def _recover_claim(self, tx, record, request, export_binding, lock, recovery):
        pause, retained_lock, current, observed = await inspect_approval_recovery(tx, recovery, request, export_binding)
        if pause != record or lock != retained_lock:
            raise ValueError("E_EPIC_APPROVAL_RECOVERY_LOCK_CHANGED")
        if observed:
            raise ValueError("E_EPIC_APPROVAL_CONTINUATION_UNCERTAIN:grant_already_consumed")
        if await self._resolved_decisions(record) != record.decisions:
            raise ValueError("E_EPIC_APPROVAL_DECISION_CONFLICT")
        await validate_approval_checkpoints(record, execution_repository=self.execution_repository,
                                           publication=self.publication, artifact_writer=self.artifact_writer)
        await retain_approval_recovery(tx, request=recovery, lock=lock, current=current, at=self.now())
        return record

    async def _resolved_decisions(self, record):
        rows, decisions = await self._requests(record.session_id), {}
        for approval_id, identity in record.approvals.items():
            self._validate_identity(record.session_id, identity)
            row = rows.get(approval_id)
            if row is None or approval_identity(row) != identity:
                raise ValueError("E_EPIC_APPROVAL_IDENTITY_CONFLICT")
            status = row["status"]
            if status == "pending":
                raise ApprovalPending("Approval required before epic continuation.")
            if (status not in {"approved", "denied"}
                    or row["resolution_json"].get("decision") != {"approved": "approve", "denied": "deny"}[status]):
                raise ValueError("E_EPIC_APPROVAL_DECISION_CONFLICT")
            decisions[approval_id] = status
        return decisions

    async def _validate_execution(self, tx: Any, pause: EpicApprovalPause) -> None:
        admission = await tx.get_admission()
        if (admission is None or admission.phase != "active" or not admission.initialization_started
                or admission.request != pause.request or admission.export_binding != pause.export_binding
                or admission.claim_ref() != pause.artifacts.get("epic_run_admission")
                or await tx.get_outcome() is not None or await tx.get_preparation() is not None or await tx.get() is not None):
            raise ValueError("E_EPIC_APPROVAL_ADMISSION_CONFLICT")
        ledger = await self.ledger.get_run(pause.session_id)
        original = pause.artifacts.get("control_plane_run_record")
        if (ledger is None or ledger["status"] != "running" or not original
                or ledger.get("artifact_json", {}).get("control_plane_run_record") != original):
            raise ValueError("E_EPIC_APPROVAL_PARENT_CONFLICT")
        run = await self.execution_repository.get_run_record(run_id=original["run_id"])
        if run is None or run.lifecycle_state != RunState.EXECUTING or run.final_truth_record_id is not None:
            raise ValueError("E_EPIC_APPROVAL_PARENT_CONFLICT")

    async def resume_turns(self, pause: EpicApprovalPause) -> dict[str, int]:
        turns = {}
        denied = "denied" in pause.decisions.values()
        for approval_id, identity in pause.approvals.items():
            target = identity["payload_json"]["control_plane_target_ref"]
            run, attempt, truth = await read_approval_execution(
                transactions=self.transactions, publication=self.publication, target=target)
            if run is None or run.namespace_scope != "issue:" + identity["issue_id"]:
                raise ValueError("E_EPIC_APPROVAL_CHILD_CONFLICT")
            if truth is not None:
                continue
            if (run.lifecycle_state != RunState.EXECUTING or attempt is None
                    or attempt.attempt_state != AttemptState.EXECUTING):
                raise ValueError("E_EPIC_APPROVAL_CHILD_CONFLICT")
            if denied:
                await stop_approval_execution(
                    transactions=self.transactions, publication=self.publication, run=run, attempt=attempt,
                    authoritative_result_ref=f"approval-request:{approval_id}:epic-stopped",
                    violation_reasons=["Epic stopped after an admitted tool approval was denied."])
            else:
                issue_id = identity["issue_id"]
                if issue_id in turns and turns[issue_id] != identity["payload_json"]["turn_index"]:
                    raise ValueError("E_EPIC_APPROVAL_MULTIPLE_UNFINISHED_TURNS")
                turns[issue_id] = identity["payload_json"]["turn_index"]
        return turns
