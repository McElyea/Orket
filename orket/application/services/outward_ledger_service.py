from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

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
    normalize_event_groups,
    verify_ledger_export,
)
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord


class OutwardLedgerValidationError(ValueError):
    pass


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

    async def export(
        self,
        run_id: str,
        *,
        types: tuple[str, ...] = (),
        include_pii: bool = False,
        operator_ref: str = "operator:api",
        record_request: bool = False,
    ) -> dict[str, Any]:
        run = await self._require_run(run_id)
        try:
            groups = normalize_event_groups(types)
        except LedgerExportValidationError as exc:
            raise OutwardLedgerValidationError(str(exc)) from exc
        export_scope = "all" if groups == ("all",) else "partial_view"
        if include_pii and record_request:
            await self._record_export_requested(
                run=run,
                groups=groups,
                export_scope=export_scope,
                include_pii=include_pii,
                operator_ref=operator_ref,
            )
        events = await self._ensure_hashes(run.run_id)
        disclosed = _disclosed_events(events, groups)
        return {
            "schema_version": SCHEMA_VERSION,
            "export_scope": export_scope,
            "run_id": run.run_id,
            "types": list(groups),
            "include_pii": bool(include_pii),
            "contains_pii": bool(include_pii),
            "summary": _summary_payload(run, events, disclosed),
            "policy_snapshot": {
                "ledger_payload_model": "policy_safe_by_construction",
                "payload_bytes": "unchanged",
                "outbound_policy_gate": "applied_before_serialization",
            },
            "canonical": {
                "ordering": ["run_id", "turn", "at", "event_id"],
                "genesis": GENESIS_CHAIN_HASH,
                "event_count": len(events),
                "ledger_hash": _ledger_hash(events),
            },
            "events": [_export_event(item) for item in disclosed],
            "omitted_spans": _omitted_spans(events, {item.position for item in disclosed}),
            "verification": {
                "result": "valid" if export_scope == "all" else "partial_valid",
                "meaning": "full canonical ledger" if export_scope == "all" else "partial verified view",
            },
        }

    async def verify_run(self, run_id: str) -> dict[str, Any]:
        payload = await self.export(run_id, types=("all",), include_pii=False, record_request=False)
        return verify_ledger_export(payload)

    async def _require_run(self, run_id: str) -> OutwardRunRecord:
        clean_run_id = str(run_id or "").strip()
        if not clean_run_id:
            raise OutwardLedgerValidationError("run_id is required")
        run = await self.run_store.get(clean_run_id)
        if run is None:
            raise OutwardLedgerValidationError(f"Run '{clean_run_id}' not found")
        return run

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
        existing_events = await self.event_store.list_for_run(run.run_id, limit=5000)
        event_id = f"run:{run.run_id}:ledger_export_requested:{len(existing_events) + 1:04d}"
        await self.event_store.append(
            LedgerEvent(
                event_id=event_id,
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
            )
        )

    async def _ensure_hashes(self, run_id: str) -> list[_HashedEvent]:
        events = await self.event_store.list_for_run(run_id, limit=5000)
        previous_chain_hash = GENESIS_CHAIN_HASH
        hashed_events: list[_HashedEvent] = []
        for position, event in enumerate(events, start=1):
            event_hash = event_hash_for(event)
            chain_hash = chain_hash_for(previous_chain_hash, event_hash)
            if event.event_hash != event_hash or event.chain_hash != chain_hash:
                await self.event_store.update_hashes(
                    event_id=event.event_id,
                    event_hash=event_hash,
                    chain_hash=chain_hash,
                )
            hashed_event = replace(event, event_hash=event_hash, chain_hash=chain_hash)
            hashed_events.append(
                _HashedEvent(event=hashed_event, position=position, previous_chain_hash=previous_chain_hash)
            )
            previous_chain_hash = chain_hash
        return hashed_events


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
