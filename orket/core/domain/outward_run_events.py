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


__all__ = ["LedgerEvent"]
