from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StateBackendContract(ABC):
    """
    Contract for runtime card-state backends.

    The execution loop remains unchanged; only persistence/work-queue I/O is swapped.
    """

    @abstractmethod
    async def fetch_ready_cards(self, *, limit: int = 1) -> list[dict[str, Any]]:
        """Fetch ready cards for execution."""

    @abstractmethod
    async def acquire_lease(
        self,
        card_id: str,
        *,
        owner_id: str,
        lease_seconds: int,
    ) -> dict[str, Any] | None:
        """Acquire a lease for a card (or return None if unavailable)."""

    @abstractmethod
    async def append_event(
        self,
        card_id: str,
        *,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Append an immutable state event for a card."""

    @abstractmethod
    async def transition_state(
        self,
        card_id: str,
        *,
        from_state: str,
        to_state: str,
        reason: str | None = None,
    ) -> None:
        """Apply a guarded card-state transition."""

    @abstractmethod
    async def release_or_fail(
        self,
        card_id: str,
        *,
        final_state: str,
        error: str | None = None,
    ) -> None:
        """Release lease and persist final state/error details."""
