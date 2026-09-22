from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction, OutwardStoreUnitOfWork
from orket.adapters.tools.registry import BuiltInConnectorRegistry
from orket.application.services.outward_authorization_service import bind_authorization
from orket.application.services.outward_connector_service import OutwardConnectorService
from orket.application.services.outward_control_plane_service import begin_outward_execution, require_outward_authority
from orket.application.services.outward_run_lifecycle import turn_completion_events
from orket.application.services.outward_terminal_service import publish_outward_terminal
from orket.core.domain.outward_approvals import OutwardApprovalProposal
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardApprovalError(RuntimeError):
    pass


class OutwardApprovalValidationError(ValueError):
    pass


class OutwardApprovalService:
    def __init__(
        self,
        *,
        approval_store: OutwardApprovalStore,
        run_store: OutwardRunStore,
        event_store: OutwardRunEventStore,
        connector_registry: BuiltInConnectorRegistry,
        utc_now: Callable[[], str],
        workspace_root: Path,
        http_allowlist: tuple[str, ...] = (),
    ) -> None:
        self.approval_store = approval_store
        self.run_store = run_store
        self.event_store = event_store
        self.connector_registry = connector_registry
        self.utc_now = utc_now
        self.connectors = OutwardConnectorService(
            connector_registry=connector_registry, workspace_root=workspace_root, http_allowlist=http_allowlist,
        )
        self.unit_of_work = OutwardStoreUnitOfWork(approvals=approval_store, runs=run_store, events=event_store)

    async def request_tool_approval(
        self,
        *,
        run_id: str,
        tool: str,
        args: dict[str, Any],
        context_summary: str,
        timeout_seconds: int = 300,
    ) -> OutwardApprovalProposal:
        args = deepcopy(args)
        async with self.unit_of_work.transaction() as transaction:
            return await self.request_in_transaction(
                transaction, run_id=run_id, tool=tool, args=args, context_summary=context_summary,
                timeout_seconds=timeout_seconds,
            )

    async def request_in_transaction(
        self, transaction: OutwardStoreTransaction, *, run_id: str, tool: str,
        args: dict[str, Any], context_summary: str, timeout_seconds: int = 300,
    ) -> OutwardApprovalProposal:
        args = deepcopy(args)
        connector = self.connector_registry.get(tool)
        if connector is None:
            raise OutwardApprovalValidationError(f"approval-required tool is not registered: {tool}")
        run = await self._require_run(run_id, transaction)
        await begin_outward_execution(transaction, run)
        if tool not in set(run.policy_overrides.get("approval_required_tools") or []):
            raise OutwardApprovalValidationError(f"tool is not approval-required for run: {tool}")
        proposal_number = await transaction.count_proposals(run.run_id) + 1
        submitted_at = self.utc_now()
        proposal = OutwardApprovalProposal(
            proposal_id=f"proposal:{run.run_id}:{tool}:{proposal_number:04d}",
            run_id=run.run_id, namespace=run.namespace, tool=tool,
            args_preview=redacted_args_preview(args, connector.pii_fields),
            context_summary=str(context_summary or "").strip(),
            risk_level=connector.risk_level,
            submitted_at=submitted_at,
            expires_at=_expires_at(submitted_at, timeout_seconds),
        )
        binding = await bind_authorization(proposal, run, args, self.connectors)
        saved = await transaction.save_proposal(replace(
            proposal, authorization_json=binding.to_json(), authorization_digest=binding.digest,
        ))
        await transaction.update_run(replace(run, status="approval_required", pending_proposals=(saved.to_queue_payload(),)))
        await self._append_event(
            transaction=transaction, run=run, event_type="proposal_pending_approval",
            proposal=saved, payload=saved.to_queue_payload(),
        )
        return saved

    async def list_pending(
        self,
        *,
        status: str | None = "pending",
        run_id: str | None = None,
        limit: int = 100,
    ) -> list[OutwardApprovalProposal]:
        await self.expire_due()
        clean_status = _normalize_status_filter(status)
        return await self.approval_store.list(status=clean_status, run_id=run_id, limit=limit)

    async def get(self, proposal_id: str) -> OutwardApprovalProposal | None:
        await self.expire_due()
        return await self.approval_store.get(proposal_id)

    async def approve(
        self,
        proposal_id: str,
        *,
        operator_ref: str,
        note: str | None = None,
    ) -> OutwardApprovalProposal:
        return await self._decide(
            proposal_id,
            status="approved",
            decision="approve",
            operator_ref=operator_ref,
            reason=None,
            note=note,
            event_type="proposal_approved",
        )

    async def deny(
        self,
        proposal_id: str,
        *,
        operator_ref: str,
        reason: str,
        note: str | None = None,
    ) -> OutwardApprovalProposal:
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise OutwardApprovalValidationError("reason is required")
        return await self._decide(
            proposal_id,
            status="denied",
            decision="deny",
            operator_ref=operator_ref,
            reason=clean_reason,
            note=note,
            event_type="proposal_denied",
        )

    async def expire_due(self) -> list[OutwardApprovalProposal]:
        now = self.utc_now()
        pending = await self.approval_store.list(status="pending", limit=500, bound_only=True)
        expired: list[OutwardApprovalProposal] = []
        for proposal in pending:
            if _parse_at(proposal.expires_at) > _parse_at(now):
                continue
            async with self.unit_of_work.transaction() as transaction:
                if await transaction.control_plane.execution.get_run_record(run_id=proposal.run_id) is None:
                    continue
            decided = await self._decide(
                proposal.proposal_id, status="expired", decision="deny", operator_ref="system:timeout",
                reason="timeout_exceeded", note=None, event_type="proposal_expired",
            )
            if decided.status == "expired":
                expired.append(decided)
        return expired

    async def _decide(
        self,
        proposal_id: str,
        *,
        status: str,
        decision: str,
        operator_ref: str,
        reason: str | None,
        note: str | None,
        event_type: str,
    ) -> OutwardApprovalProposal:
        async with self.unit_of_work.transaction() as transaction:
            proposal = await transaction.get_proposal(proposal_id)
            if proposal is None:
                raise OutwardApprovalValidationError(f"Approval proposal '{proposal_id}' not found")
            if proposal.status != "pending":
                return proposal
            if proposal.authorization is None:
                raise OutwardApprovalError("E_OUTWARD_AUTHORIZATION_REQUIRED")
            # The unit of work acquired the SQLite writer lock before this clock sample.
            now = self.utc_now()
            if _parse_at(now) >= _parse_at(proposal.expires_at):
                status, decision, operator_ref = "expired", "deny", "system:timeout"
                reason, note, event_type = "timeout_exceeded", None, "proposal_expired"
            elif status == "expired":
                return proposal
            decided = replace(
                proposal, status=status, decision=decision,
                operator_ref=str(operator_ref or "").strip() or "operator:unknown",
                reason=reason, note=note, decided_at=now,
            )
            if not await transaction.decide_proposal(decided):
                raise OutwardApprovalError("E_OUTWARD_DECISION_CONFLICT")
            run = await self._require_run(decided.run_id, transaction)
            await self._append_event(
                transaction=transaction, run=run, event_type=event_type,
                proposal=decided, payload=decided.to_decision_payload(),
            )
            if status == "approved":
                await transaction.update_run(replace(run, status="running", pending_proposals=()))
            else:
                for event in turn_completion_events(run, decided.tool, decided.proposal_id, at=now,
                        outcome=status, record_commitment=False):
                    await transaction.append_event(event)
                await publish_outward_terminal(transaction, run, at=now, outcome=status, reason=reason, cause=decided)
            return decided

    async def _require_run(self, run_id: str, transaction: OutwardStoreTransaction) -> OutwardRunRecord:
        run = await transaction.get_run(run_id)
        if run is None:
            raise OutwardApprovalValidationError(f"Run '{run_id}' not found")
        run.require_execution_admission()
        await require_outward_authority(transaction, run)
        return run

    async def _append_event(
        self,
        *,
        transaction: OutwardStoreTransaction,
        run: OutwardRunRecord,
        event_type: str,
        proposal: OutwardApprovalProposal,
        payload: dict[str, Any],
    ) -> None:
        event_id = f"{proposal.proposal_id}:{_event_order(event_type)}:{event_type}"
        if await transaction.get_event(event_id) is not None:
            raise OutwardApprovalError("E_OUTWARD_DECISION_HISTORY_CONFLICT")
        await transaction.append_event(
            LedgerEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=proposal.run_id,
                turn=run.current_turn,
                agent_id="operator",
                at=proposal.decided_at or proposal.submitted_at,
                payload=payload,
            )
        )


def _normalize_status_filter(status: str | None) -> str | None:
    clean = str(status or "").strip().lower()
    return clean or None


def redacted_args_preview(args: dict[str, Any], pii_fields: tuple[str, ...]) -> dict[str, Any]:
    redacted = dict(args)
    for field in pii_fields:
        if field in redacted:
            redacted[field] = "[REDACTED]"
    return redacted


def _expires_at(submitted_at: str, timeout_seconds: int) -> str:
    return (_parse_at(submitted_at) + timedelta(seconds=max(1, int(timeout_seconds)))).isoformat()


def _parse_at(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed


def _event_order(event_type: str) -> str:
    if event_type == "proposal_pending_approval":
        return "0001"
    return "0002"


__all__ = [
    "OutwardApprovalError",
    "OutwardApprovalService",
    "OutwardApprovalValidationError",
    "redacted_args_preview",
]
