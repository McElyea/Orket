from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional


class GiteaStateWorker:
    """
    Lightweight multi-runner worker loop over GiteaStateAdapter semantics.
    """

    def __init__(
        self,
        *,
        adapter: Any,
        worker_id: str,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        success_state: str = "code_review",
        failure_state: str = "blocked",
    ):
        self.adapter = adapter
        self.worker_id = str(worker_id)
        self.lease_seconds = max(1, int(lease_seconds))
        self.renew_interval_seconds = max(0.1, float(renew_interval_seconds))
        self.success_state = str(success_state)
        self.failure_state = str(failure_state)

    async def run_once(
        self,
        *,
        work_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        fetch_limit: int = 5,
    ) -> bool:
        candidates = await self.adapter.fetch_ready_cards(limit=max(1, int(fetch_limit)))
        for candidate in candidates:
            card_id = str(candidate.get("issue_number") or candidate.get("card_id") or "").strip()
            if not card_id:
                continue
            lease = await self.adapter.acquire_lease(
                card_id,
                owner_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )
            if not lease:
                continue
            await self._run_claimed(card_id=card_id, card=candidate, work_fn=work_fn)
            return True
        return False

    async def _run_claimed(
        self,
        *,
        card_id: str,
        card: Dict[str, Any],
        work_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    ) -> None:
        from_state = str(card.get("state") or "ready")
        await self.adapter.transition_state(
            card_id,
            from_state=from_state,
            to_state="in_progress",
            reason=f"worker_claimed:{self.worker_id}",
        )
        stop_event = asyncio.Event()
        renew_task = asyncio.create_task(self._renew_loop(card_id=card_id, stop_event=stop_event))
        try:
            await work_fn(card)
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.success_state,
                error=None,
            )
        except (RuntimeError, ValueError, TypeError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.failure_state,
                error=str(exc),
            )
        finally:
            stop_event.set()
            try:
                await renew_task
            except asyncio.CancelledError:
                pass

    async def _renew_loop(self, *, card_id: str, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.renew_interval_seconds)
                break
            except (TimeoutError, asyncio.TimeoutError):
                await self.adapter.renew_lease(
                    card_id,
                    owner_id=self.worker_id,
                    lease_seconds=self.lease_seconds,
                )
