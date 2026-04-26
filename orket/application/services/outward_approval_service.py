from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from orket.adapters.storage.outward_approval_store import OutwardApprovalStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.tools.registry import BuiltInConnectorRegistry
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
    ) -> None:
        self.approval_store = approval_store
        self.run_store = run_store
        self.event_store = event_store
        self.connector_registry = connector_registry
        self.utc_now = utc_now

    async def request_tool_approval(
        self,
        *,
        run_id: str,
        tool: str,
        args: dict[str, Any],
        context_summary: str,
        timeout_seconds: int = 300,
    ) -> OutwardApprovalProposal:
        run = await self._require_run(run_id)
        connector = self.connector_registry.get(tool)
        if connector is None:
            raise OutwardApprovalValidationError(f"approval-required tool is not registered: {tool}")
        required_tools = set(run.policy_overrides.get("approval_required_tools") or [])
        if tool not in required_tools:
            raise OutwardApprovalValidationError(f"tool is not approval-required for run: {tool}")

        proposal = OutwardApprovalProposal(
            proposal_id=f"proposal:{run.run_id}:{tool}:0001",
            run_id=run.run_id,
            namespace=run.namespace,
            tool=tool,
            args_preview=redacted_args_preview(args, connector.pii_fields),
            context_summary=str(context_summary or "").strip(),
            risk_level=connector.risk_level,
            submitted_at=self.utc_now(),
            expires_at=_expires_at(self.utc_now(), timeout_seconds),
        )
        existing = await self.approval_store.get(proposal.proposal_id)
        if existing is not None:
            return existing
        saved = await self.approval_store.save(proposal)
        await self.run_store.update(
            replace(
                run,
                status="approval_required",
                pending_proposals=(saved.to_queue_payload(),),
            )
        )
        await self._append_event(
            event_type="proposal_pending_approval",
            proposal=saved,
            payload=saved.to_queue_payload(),
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
        pending = await self.approval_store.list(status="pending", limit=500)
        expired: list[OutwardApprovalProposal] = []
        for proposal in pending:
            if _parse_at(proposal.expires_at) > _parse_at(now):
                continue
            expired.append(
                await self._decide(
                    proposal.proposal_id,
                    status="expired",
                    decision="deny",
                    operator_ref="system:timeout",
                    reason="timeout_exceeded",
                    note=None,
                    event_type="proposal_expired",
                )
            )
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
        proposal = await self.approval_store.get(proposal_id)
        if proposal is None:
            raise OutwardApprovalValidationError(f"Approval proposal '{proposal_id}' not found")
        if proposal.status != "pending":
            return proposal
        decided = replace(
            proposal,
            status=status,
            decision=decision,
            operator_ref=str(operator_ref or "").strip() or "operator:unknown",
            reason=reason,
            note=note,
            decided_at=self.utc_now(),
        )
        saved = await self.approval_store.save(decided)
        run = await self._require_run(saved.run_id)
        if status == "approved":
            await self.run_store.update(replace(run, status="running", pending_proposals=()))
        else:
            await self.run_store.update(
                replace(
                    run,
                    status="failed",
                    pending_proposals=(),
                    completed_at=saved.decided_at,
                    stop_reason=saved.reason,
                )
            )
        await self._append_event(event_type=event_type, proposal=saved, payload=saved.to_decision_payload())
        return saved

    async def _require_run(self, run_id: str) -> OutwardRunRecord:
        run = await self.run_store.get(run_id)
        if run is None:
            raise OutwardApprovalValidationError(f"Run '{run_id}' not found")
        return run

    async def _append_event(
        self,
        *,
        event_type: str,
        proposal: OutwardApprovalProposal,
        payload: dict[str, Any],
    ) -> None:
        event_id = f"{proposal.proposal_id}:{_event_order(event_type)}:{event_type}"
        if await self.event_store.get(event_id) is not None:
            return
        run = await self.run_store.get(proposal.run_id)
        await self.event_store.append(
            LedgerEvent(
                event_id=event_id,
                event_type=event_type,
                run_id=proposal.run_id,
                turn=run.current_turn if run is not None else 0,
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
