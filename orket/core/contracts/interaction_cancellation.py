"""Observed cancellation of a selected interaction; no ambient inputs or effects."""
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class InteractionCancellation:
    status: Literal["cancelled", "not_found", "idle", "terminal"]
    session_id: str | None
    turn_id: str | None
    timestamp: str | None
