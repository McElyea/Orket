from __future__ import annotations

from collections import Counter
from typing import Any

from orket.adapters.storage.outward_run_event_store import OutwardRunEventStore
from orket.adapters.storage.outward_run_store import OutwardRunStore
from orket.adapters.storage.outward_store_transaction import OutwardStoreUnitOfWork
from orket.application.services.outward_control_plane_service import outward_status_payload
from orket.core.domain.outward_run_events import LedgerEvent


class OutwardRunInspectionError(ValueError):
    pass


class OutwardRunInspectionService:
    def __init__(self, *, run_store: OutwardRunStore, event_store: OutwardRunEventStore,
                 unit_of_work: OutwardStoreUnitOfWork | None = None) -> None:
        self.run_store = run_store
        self.event_store = event_store
        self.unit_of_work = unit_of_work or OutwardStoreUnitOfWork.for_run_stores(run_store, event_store)

    async def events(
        self,
        run_id: str,
        *,
        from_turn: int | None = None,
        to_turn: int | None = None,
        types: tuple[str, ...] = (),
        agent_id: str | None = None,
        limit: int = 1000,
    ) -> dict[str, Any]:
        clean_run_id = _require_run_id(run_id)
        if await self.run_store.get(clean_run_id) is None:
            raise OutwardRunInspectionError(f"Run '{clean_run_id}' not found")
        events = await self.event_store.list_for_run(
            clean_run_id,
            from_turn=from_turn,
            to_turn=to_turn,
            types=types,
            agent_id=agent_id,
            limit=limit,
        )
        return {
            "run_id": clean_run_id,
            "events": [_event_payload(event) for event in events],
            "count": len(events),
            "filters": {
                "from_turn": from_turn,
                "to_turn": to_turn,
                "types": list(types),
                "agent_id": agent_id,
            },
        }

    async def summary(self, run_id: str) -> dict[str, Any]:
        clean_run_id = _require_run_id(run_id)
        async with self.unit_of_work.transaction() as transaction:
            run = await transaction.get_run(clean_run_id)
            if run is None:
                raise OutwardRunInspectionError(f"Run '{clean_run_id}' not found")
            authority = await outward_status_payload(transaction, run)
            events = await self.event_store.list_for_run(clean_run_id)
        counts = Counter(event.event_type for event in events)
        return {
            "run_id": clean_run_id,
            "status": run.status,
            "authority_state": authority["authority_state"],
            "final_truth": authority["final_truth"],
            "current_turn": run.current_turn,
            "max_turns": run.max_turns,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "stop_reason": run.stop_reason,
            "pending_proposals_count": len(run.pending_proposals),
            "event_count": len(events),
            "event_counts": dict(sorted(counts.items())),
            "terminal": run.status in {"completed", "failed"},
        }


def _require_run_id(run_id: str) -> str:
    clean = str(run_id or "").strip()
    if not clean:
        raise OutwardRunInspectionError("run_id is required")
    return clean


def _event_payload(event: LedgerEvent) -> dict[str, Any]:
    return {
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


__all__ = ["OutwardRunInspectionError", "OutwardRunInspectionService"]
