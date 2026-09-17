from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    event_type: str
    run_id: str
    turn: int | None
    agent_id: str | None
    at: str
    payload: dict[str, Any]
    event_hash: str | None = None
    chain_hash: str | None = None


def validate_ledger_event(event: LedgerEvent) -> None:
    for field in ("event_id", "event_type", "run_id", "at"):
        if not isinstance(getattr(event, field), str) or not getattr(event, field).strip():
            raise ValueError(f"{field} is required")
    if event.turn is not None and type(event.turn) is not int:
        raise ValueError("turn must be an integer or null")
    if not isinstance(event.payload, dict) or (event.agent_id is not None and not isinstance(event.agent_id, str)):
        raise ValueError("payload must be an object and agent_id must be a string or null")


__all__ = ["LedgerEvent", "validate_ledger_event"]
