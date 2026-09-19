from __future__ import annotations

import asyncio
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from orket.adapters.storage.outward_ledger_file_store import OutwardLedgerFileStore
from orket.adapters.storage.outward_ledger_snapshot_store import OutwardLedgerSnapshotStore
from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.core.domain.outward_ledger import (
    GENESIS_CHAIN_HASH,
    LEDGER_EXPORT_REQUESTED,
    SCHEMA_VERSION,
    LedgerExportValidationError,
    chain_hash_for,
    event_group,
    event_hash_for,
    event_order_key,
    normalize_event_groups,
    verify_ledger_export,
)
from orket.core.domain.outward_ledger_integrity import OutwardLedgerIntegrityError, RetainedLedgerSnapshot
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardLedgerValidationError(ValueError):
    pass


async def verify_ledger_file(path: Path) -> dict[str, Any]:
    """Offline verification owns the selected read and applies the canonical core verifier."""
    payload = await OutwardLedgerFileStore().read(path)
    return verify_ledger_export(payload)


@dataclass(frozen=True)
class _HashedEvent:
    event: LedgerEvent
    position: int
    previous_chain_hash: str


class OutwardLedgerService:
    def __init__(
        self,
        *,
        run_store: OutwardRunStore,
        event_store: OutwardRunEventStore,
        utc_now: Callable[[], str],
    ) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.utc_now = utc_now
        self.snapshot_store = OutwardLedgerSnapshotStore(event_store.db_path)

    async def export(
        self,
        run_id: str,
        *,
        types: tuple[str, ...] = (),
        include_pii: bool = False,
        operator_ref: str = "operator:api",
        record_request: bool = False,
    ) -> dict[str, Any]:
        try:
            groups = normalize_event_groups(types)
        except LedgerExportValidationError as exc:
            raise OutwardLedgerValidationError(str(exc)) from exc
        try:
            snapshot = await self._snapshot(run_id)
            if include_pii and record_request:
                await self._record_export_requested(
                    run=snapshot.run, groups=groups,
                    export_scope="all" if groups == ("all",) else "partial_view",
                    include_pii=include_pii, operator_ref=operator_ref,
                )
                snapshot = await self._snapshot(run_id)
        except OutwardLedgerIntegrityError as exc:
            raise OutwardLedgerValidationError(str(exc)) from exc
        return _build_export(snapshot, groups, include_pii)

    async def verify_run(
        self, run_id: str, *, external_anchor: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            snapshot = await self._snapshot(run_id)
        except OutwardLedgerIntegrityError as exc:
            if exc.category == "not_found":
                raise OutwardLedgerValidationError(str(exc)) from exc
            return {
                "schema_version": SCHEMA_VERSION, "result": "invalid", "run_id": run_id,
                "export_scope": "all", "ledger_hash": None, "event_count": None,
                "checked_event_count": 0, "errors": [str(exc)],
                "retained_integrity": "invalid" if exc.category == "integrity" else "not_verified",
                "snapshot_completeness": "not_verified", "authenticity": "not_established",
                "external_anchor": "not_checked",
            }
        report = verify_ledger_export(_build_export(snapshot, ("all",), False))
        report.update({
            "retained_integrity": "valid", "snapshot_completeness": "valid",
            "retained_anchor": snapshot.anchor.to_dict(), "authenticity": "not_established",
            "external_anchor": "not_supplied",
        })
        if external_anchor is not None:
            try:
                snapshot.compare_anchor(external_anchor)
                report["external_anchor"] = "matched_prefix"
            except OutwardLedgerIntegrityError as exc:
                report["result"], report["external_anchor"] = "invalid", "invalid"
                report["errors"].append(str(exc))
        return report

    async def _snapshot(self, run_id: str) -> RetainedLedgerSnapshot:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise OutwardLedgerValidationError("run_id is required")
        paths = await asyncio.to_thread(lambda: (self.run_store.db_path.resolve(), self.event_store.db_path.resolve()))
        if paths[0] != paths[1]:
            raise OutwardLedgerValidationError("E_OUTWARD_TRANSACTION_DATABASE_MISMATCH")
        return await self.snapshot_store.read(clean_run_id)

    async def _record_export_requested(
        self,
        *,
        run: OutwardRunRecord,
        groups: tuple[str, ...],
        export_scope: str,
        include_pii: bool,
        operator_ref: str,
    ) -> None:
        requested_at = self.utc_now()
        async with self.event_store.writer(run.run_id) as writer:
            await writer.append(LedgerEvent(
                event_id=f"run:{run.run_id}:ledger_export_requested:{writer.next_sequence:04d}",
                event_type=LEDGER_EXPORT_REQUESTED,
                run_id=run.run_id,
                turn=run.current_turn,
                agent_id="operator",
                at=requested_at,
                payload={
                    "run_id": run.run_id,
                    "operator_ref": str(operator_ref or "").strip() or "operator:unknown",
                    "include_pii": bool(include_pii),
                    "export_scope": export_scope,
                    "types": list(groups),
                    "requested_at": requested_at,
                },
            ))


def _project_v1(events: tuple[LedgerEvent, ...]) -> list[_HashedEvent]:
    ordered = sorted(events, key=event_order_key)
    previous = GENESIS_CHAIN_HASH
    projected = []
    for position, event in enumerate(ordered, start=1):
        digest = event_hash_for(event)
        chain = chain_hash_for(previous, digest)
        projected.append(_HashedEvent(replace(event, event_hash=digest, chain_hash=chain), position, previous))
        previous = chain
    return projected


def _build_export(snapshot: RetainedLedgerSnapshot, groups: tuple[str, ...], include_pii: bool) -> dict[str, Any]:
    run, events = snapshot.run, _project_v1(snapshot.events)
    disclosed = _disclosed_events(events, groups)
    scope = "all" if groups == ("all",) else "partial_view"
    return {
        "schema_version": SCHEMA_VERSION, "export_scope": scope, "run_id": run.run_id,
        "types": list(groups), "include_pii": bool(include_pii), "contains_pii": bool(include_pii),
        "summary": _summary_payload(run, events, disclosed),
        "policy_snapshot": {
            "ledger_payload_model": "policy_safe_by_construction", "payload_bytes": "unchanged",
            "outbound_policy_gate": "applied_before_serialization",
        },
        "canonical": {
            "ordering": ["run_id", "turn", "at", "event_id"], "genesis": GENESIS_CHAIN_HASH,
            "event_count": snapshot.independent_count, "ledger_hash": _ledger_hash(events),
        },
        "retained": {
            "anchor": snapshot.anchor.to_dict(), "integrity": "valid", "snapshot_completeness": "valid",
            "authenticity": "not_established", "authority": "runtime_assertion",
        },
        "events": [_export_event(item) for item in disclosed],
        "omitted_spans": _omitted_spans(events, {item.position for item in disclosed}),
        "verification": {
            "result": "valid" if scope == "all" else "partial_valid",
            "meaning": "full canonical ledger" if scope == "all" else "partial verified view",
        },
    }


def _disclosed_events(events: list[_HashedEvent], groups: tuple[str, ...]) -> list[_HashedEvent]:
    if groups == ("all",):
        return list(events)
    return [item for item in events if event_group(item.event.event_type) in groups]


def _summary_payload(
    run: OutwardRunRecord,
    events: list[_HashedEvent],
    disclosed: list[_HashedEvent],
) -> dict[str, Any]:
    counts = Counter(item.event.event_type for item in events)
    return {
        "run_id": run.run_id,
        "status": run.status,
        "current_turn": run.current_turn,
        "max_turns": run.max_turns,
        "completed_at": run.completed_at,
        "stop_reason": run.stop_reason,
        "event_count": len(events),
        "exported_event_count": len(disclosed),
        "event_counts": dict(sorted(counts.items())),
    }


def _ledger_hash(events: list[_HashedEvent]) -> str:
    if not events:
        return GENESIS_CHAIN_HASH
    return str(events[-1].event.chain_hash)


def _export_event(item: _HashedEvent) -> dict[str, Any]:
    event = item.event
    return {
        "position": item.position,
        "event_group": event_group(event.event_type),
        "previous_chain_hash": item.previous_chain_hash,
        "event_id": event.event_id,
        "event_type": event.event_type,
        "run_id": event.run_id,
        "turn": event.turn,
        "agent_id": event.agent_id,
        "at": event.at,
        "payload": dict(event.payload),
        "event_hash": event.event_hash,
        "chain_hash": event.chain_hash,
    }


def _omitted_spans(events: list[_HashedEvent], disclosed_positions: set[int]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    position = 1
    while position <= len(events):
        if position in disclosed_positions:
            position += 1
            continue
        start = position
        while position <= len(events) and position not in disclosed_positions:
            position += 1
        end = position - 1
        previous_chain_hash = GENESIS_CHAIN_HASH if start == 1 else str(events[start - 2].event.chain_hash)
        next_chain_hash = str(events[end - 1].event.chain_hash)
        spans.append(
            {
                "from_position": start,
                "to_position": end,
                "previous_chain_hash": previous_chain_hash,
                "next_chain_hash": next_chain_hash,
            }
        )
    return spans


__all__ = ["OutwardLedgerService", "OutwardLedgerValidationError", "verify_ledger_export"]
