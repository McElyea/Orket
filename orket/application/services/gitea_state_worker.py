from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Dict


class LeaseExpiredError(RuntimeError):
    """Raised when lease renewal fails or lease epoch changes unexpectedly."""


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
            await self._run_claimed(
                card_id=card_id,
                card=candidate,
                work_fn=work_fn,
                lease_epoch=self._lease_epoch(lease),
            )
            return True
        return False

    async def _run_claimed(
        self,
        *,
        card_id: str,
        card: Dict[str, Any],
        work_fn: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
        lease_epoch: int | None,
    ) -> None:
        from_state = str(card.get("state") or "ready")
        await self.adapter.transition_state(
            card_id,
            from_state=from_state,
            to_state="in_progress",
            reason=f"worker_claimed:{self.worker_id}",
        )
        stop_event = asyncio.Event()
        lease_state = {"expired": False, "reason": ""}
        renew_task = asyncio.create_task(
            self._renew_loop(
                card_id=card_id,
                stop_event=stop_event,
                lease_epoch=lease_epoch,
                lease_state=lease_state,
            )
        )
        try:
            await work_fn(card)
            if lease_state["expired"]:
                raise LeaseExpiredError(lease_state["reason"] or "E_LEASE_EXPIRED")
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.success_state,
                error=None,
            )
        except LeaseExpiredError as exc:
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.failure_state,
                error=str(exc) or "E_LEASE_EXPIRED",
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

    async def _renew_loop(
        self,
        *,
        card_id: str,
        stop_event: asyncio.Event,
        lease_epoch: int | None,
        lease_state: Dict[str, Any],
    ) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.renew_interval_seconds)
                break
            except (TimeoutError, asyncio.TimeoutError):
                renewed = await self._renew_lease(card_id=card_id, lease_epoch=lease_epoch)
                if self._is_lease_expired(renewed, expected_epoch=lease_epoch):
                    lease_state["expired"] = True
                    lease_state["reason"] = "E_LEASE_EXPIRED"
                    stop_event.set()
                    break

    async def _renew_lease(self, *, card_id: str, lease_epoch: int | None) -> Any:
        try:
            return await self.adapter.renew_lease(
                card_id,
                owner_id=self.worker_id,
                lease_seconds=self.lease_seconds,
                expected_lease_epoch=lease_epoch,
            )
        except TypeError:
            return await self.adapter.renew_lease(
                card_id,
                owner_id=self.worker_id,
                lease_seconds=self.lease_seconds,
            )

    @staticmethod
    def _is_lease_expired(renewed: Any, *, expected_epoch: int | None) -> bool:
        if isinstance(renewed, dict):
            if str(renewed.get("error_code") or "").strip().upper() == "E_LEASE_EXPIRED":
                return True
            if renewed.get("ok") is False:
                return True
            actual_epoch = renewed.get("lease_epoch")
            if expected_epoch is not None and actual_epoch is not None:
                try:
                    if int(actual_epoch) != int(expected_epoch):
                        return True
                except (TypeError, ValueError):
                    return True
        return False

    @staticmethod
    def _lease_epoch(lease: Any) -> int | None:
        if not isinstance(lease, dict):
            return None
        raw = lease.get("lease_epoch")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None
