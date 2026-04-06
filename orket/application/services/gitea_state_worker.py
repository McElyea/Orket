from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from orket.application.services.control_plane_resource_authority_checks import (
    require_resource_snapshot_matches_lease,
)
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    GiteaStateControlPlaneCheckpointService,
)
from orket.application.services.gitea_state_control_plane_claim_failure_service import close_gitea_state_claim_failure
from orket.application.services.gitea_state_control_plane_execution_service import (
    GiteaStateControlPlaneExecutionService,
)
from orket.application.services.gitea_state_control_plane_lease_service import GiteaStateControlPlaneLeaseService
from orket.application.services.gitea_state_control_plane_reservation_service import (
    GiteaStateControlPlaneReservationService,
)


class LeaseExpiredError(RuntimeError):
    """Raised when lease renewal fails or lease epoch changes unexpectedly."""


class GiteaStateWorker:
    """Lightweight multi-runner worker loop over GiteaStateAdapter semantics."""

    CONTROL_PLANE_RESOURCE_DRIFT_REASON = "E_CONTROL_PLANE_RESOURCE_DRIFT"

    def __init__(
        self,
        *,
        adapter: Any,
        worker_id: str,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        success_state: str = "code_review",
        failure_state: str = "blocked",
        control_plane_checkpoint_service: GiteaStateControlPlaneCheckpointService | None = None,
        control_plane_execution_service: GiteaStateControlPlaneExecutionService | None = None,
        control_plane_lease_service: GiteaStateControlPlaneLeaseService | None = None,
        control_plane_reservation_service: GiteaStateControlPlaneReservationService | None = None,
    ):
        self.adapter = adapter
        self.worker_id = str(worker_id)
        self.lease_seconds = max(1, int(lease_seconds))
        self.renew_interval_seconds = max(0.1, float(renew_interval_seconds))
        self.success_state = str(success_state)
        self.failure_state = str(failure_state)
        self.control_plane_checkpoint_service = control_plane_checkpoint_service
        self.control_plane_execution_service = control_plane_execution_service
        self.control_plane_lease_service = control_plane_lease_service
        self.control_plane_reservation_service = control_plane_reservation_service

    async def run_once(
        self,
        *,
        work_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        fetch_limit: int = 5,
    ) -> bool:
        candidates = await self.adapter.fetch_ready_cards(limit=max(1, int(fetch_limit)))
        for candidate in candidates:
            card_id = str(candidate.get("issue_number") or candidate.get("card_id") or "").strip()
            if not card_id:
                continue
            lease = await self.adapter.acquire_lease(card_id, owner_id=self.worker_id, lease_seconds=self.lease_seconds)
            if not lease:
                continue
            reservation_id = await self._publish_claim_reservation_if_enabled(card_id=card_id, lease_observation=lease)
            await self._publish_claimed_lease_if_enabled(
                card_id=card_id,
                lease_observation=lease,
                source_reservation_id=reservation_id,
            )
            run, attempt = await self._begin_claimed_execution_if_enabled(
                card_id=card_id,
                card=candidate,
                lease_observation=lease,
            )
            await self._publish_pre_effect_checkpoint_if_enabled(
                card_id=card_id,
                card=candidate,
                lease_observation=lease,
                run=run,
                attempt=attempt,
            )
            await self._run_claimed(
                card_id=card_id,
                card=candidate,
                work_fn=work_fn,
                lease_epoch=self._lease_epoch(lease),
                lease_observation=lease if isinstance(lease, dict) else None,
                control_plane_run_id=None if run is None else run.run_id,
                control_plane_attempt_id=None if attempt is None else attempt.attempt_id,
                control_plane_reservation_id=reservation_id,
            )
            return True
        return False

    async def _run_claimed(
        self,
        *,
        card_id: str,
        card: dict[str, Any],
        work_fn: Callable[[dict[str, Any]], Awaitable[dict[str, Any]]],
        lease_epoch: int | None,
        lease_observation: dict[str, Any] | None,
        control_plane_run_id: str | None,
        control_plane_attempt_id: str | None,
        control_plane_reservation_id: str | None,
    ) -> None:
        from_state = str(card.get("state") or "ready")
        try:
            await self.adapter.transition_state(
                card_id,
                from_state=from_state,
                to_state="in_progress",
                reason=f"worker_claimed:{self.worker_id}",
            )
        except (RuntimeError, ValueError, TypeError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            handled = await close_gitea_state_claim_failure(
                execution_service=self.control_plane_execution_service,
                lease_service=self.control_plane_lease_service,
                card_id=card_id,
                worker_id=self.worker_id,
                from_state=from_state,
                error=str(exc),
                lease_observation=lease_observation,
                run_id=control_plane_run_id,
                attempt_id=control_plane_attempt_id,
                reservation_service=self.control_plane_reservation_service,
            )
            if isinstance(exc, ValueError) and handled:
                return
            raise
        await self._publish_claim_transition_if_enabled(card_id=card_id, from_state=from_state, control_plane_run_id=control_plane_run_id, control_plane_attempt_id=control_plane_attempt_id)
        await self._promote_claim_reservation_if_enabled(
            card_id=card_id,
            lease_epoch=lease_epoch,
            reservation_id=control_plane_reservation_id,
        )
        stop_event = asyncio.Event()
        lease_state = {
            "expired": False,
            "authority_drift": False,
            "reason": "",
            "lease_observation": lease_observation,
        }
        renew_task = asyncio.create_task(self._renew_loop(card_id=card_id, stop_event=stop_event, lease_epoch=lease_epoch, lease_state=lease_state))
        try:
            await work_fn(card)
            if lease_state["expired"]:
                await self._publish_expired_lease_if_enabled(
                    card_id=card_id,
                    lease_observation=lease_state["lease_observation"],
                    reason=lease_state["reason"] or "E_LEASE_EXPIRED",
                )
                raise LeaseExpiredError(lease_state["reason"] or "E_LEASE_EXPIRED")
            if lease_state["authority_drift"]:
                drift_reason = lease_state["reason"] or self.CONTROL_PLANE_RESOURCE_DRIFT_REASON
                await self.adapter.release_or_fail(
                    card_id,
                    final_state=self.failure_state,
                    error=drift_reason,
                )
                await self._publish_release_transition_if_enabled(
                    card_id=card_id,
                    final_state=self.failure_state,
                    error=drift_reason,
                    control_plane_run_id=control_plane_run_id,
                    control_plane_attempt_id=control_plane_attempt_id,
                )
                await self._publish_released_lease_if_enabled(
                    card_id=card_id,
                    lease_observation=lease_state["lease_observation"],
                    final_state=self.failure_state,
                )
                return
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.success_state,
                error=None,
            )
            await self._publish_release_transition_if_enabled(
                card_id=card_id,
                final_state=self.success_state,
                error=None,
                control_plane_run_id=control_plane_run_id,
                control_plane_attempt_id=control_plane_attempt_id,
            )
            await self._publish_released_lease_if_enabled(
                card_id=card_id,
                lease_observation=lease_state["lease_observation"],
                final_state=self.success_state,
            )
        except LeaseExpiredError as exc:
            if lease_state["expired"]:
                await self._publish_expired_lease_if_enabled(
                    card_id=card_id,
                    lease_observation=lease_state["lease_observation"],
                    reason=lease_state["reason"] or str(exc) or "E_LEASE_EXPIRED",
                )
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.failure_state,
                error=str(exc) or "E_LEASE_EXPIRED",
            )
            await self._publish_release_transition_if_enabled(
                card_id=card_id,
                final_state=self.failure_state,
                error=str(exc) or "E_LEASE_EXPIRED",
                control_plane_run_id=control_plane_run_id,
                control_plane_attempt_id=control_plane_attempt_id,
            )
        except (RuntimeError, ValueError, TypeError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            effective_error = (
                lease_state["reason"]
                if lease_state.get("authority_drift")
                else str(exc)
            )
            await self.adapter.release_or_fail(
                card_id,
                final_state=self.failure_state,
                error=effective_error,
            )
            await self._publish_release_transition_if_enabled(
                card_id=card_id,
                final_state=self.failure_state,
                error=effective_error,
                control_plane_run_id=control_plane_run_id,
                control_plane_attempt_id=control_plane_attempt_id,
            )
            if lease_state["expired"]:
                await self._publish_expired_lease_if_enabled(
                    card_id=card_id,
                    lease_observation=lease_state["lease_observation"],
                    reason=lease_state["reason"] or effective_error or "E_LEASE_EXPIRED",
                )
            else:
                await self._publish_released_lease_if_enabled(
                    card_id=card_id,
                    lease_observation=lease_state["lease_observation"],
                    final_state=self.failure_state,
                )
        finally:
            stop_event.set()
            with contextlib.suppress(asyncio.CancelledError):
                await renew_task

    async def _renew_loop(
        self,
        *,
        card_id: str,
        stop_event: asyncio.Event,
        lease_epoch: int | None,
        lease_state: dict[str, Any],
    ) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=self.renew_interval_seconds)
                break
            except (TimeoutError, asyncio.TimeoutError):
                if await self._control_plane_renewal_authority_drifted(card_id=card_id):
                    lease_state["authority_drift"] = True
                    lease_state["reason"] = self.CONTROL_PLANE_RESOURCE_DRIFT_REASON
                    stop_event.set()
                    break
                renewed = await self._renew_lease(card_id=card_id, lease_epoch=lease_epoch)
                if self._is_lease_expired(renewed, expected_epoch=lease_epoch):
                    lease_state["expired"] = True
                    lease_state["reason"] = "E_LEASE_EXPIRED"
                    stop_event.set()
                    break
                if isinstance(renewed, dict) and self._lease_epoch(renewed) is not None:
                    lease_state["lease_observation"] = renewed
                    try:
                        await self._publish_renewed_lease_if_enabled(card_id=card_id, lease_observation=renewed)
                    except ValueError:
                        lease_state["authority_drift"] = True
                        lease_state["reason"] = self.CONTROL_PLANE_RESOURCE_DRIFT_REASON
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
            actual_epoch = GiteaStateWorker._lease_epoch(renewed)
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
        nested = lease.get("lease")
        raw = nested.get("epoch") if isinstance(nested, dict) else lease.get("lease_epoch")
        if raw is None:
            return None
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    async def _publish_claim_reservation_if_enabled(self, *, card_id: str, lease_observation: Any) -> str | None:
        if self.control_plane_reservation_service is None or not isinstance(lease_observation, dict):
            return None
        lease_epoch = self._lease_epoch(lease_observation)
        if lease_epoch is None:
            return None
        reservation = await self.control_plane_reservation_service.publish_claim_reservation(
            card_id=card_id,
            worker_id=self.worker_id,
            lease_epoch=lease_epoch,
        )
        return reservation.reservation_id

    async def _publish_claimed_lease_if_enabled(
        self,
        *,
        card_id: str,
        lease_observation: Any,
        source_reservation_id: str | None,
    ) -> None:
        if self.control_plane_lease_service is None or not isinstance(lease_observation, dict):
            return
        await self.control_plane_lease_service.publish_claimed_lease(
            card_id=card_id,
            worker_id=self.worker_id,
            lease_observation=lease_observation,
            lease_seconds=self.lease_seconds,
            source_reservation_id=source_reservation_id,
        )

    async def _promote_claim_reservation_if_enabled(
        self,
        *,
        card_id: str,
        lease_epoch: int | None,
        reservation_id: str | None,
    ) -> None:
        if (
            self.control_plane_reservation_service is None
            or reservation_id is None
            or lease_epoch is None
        ):
            return
        await self.control_plane_reservation_service.promote_claim_reservation(
            card_id=card_id,
            lease_epoch=lease_epoch,
        )

    async def _publish_renewed_lease_if_enabled(self, *, card_id: str, lease_observation: Any) -> None:
        if self.control_plane_lease_service is None or not isinstance(lease_observation, dict):
            return
        await self.control_plane_lease_service.publish_renewed_lease(
            card_id=card_id,
            worker_id=self.worker_id,
            lease_observation=lease_observation,
            lease_seconds=self.lease_seconds,
        )

    async def _control_plane_renewal_authority_drifted(self, *, card_id: str) -> bool:
        if self.control_plane_lease_service is None:
            return False
        try:
            await self.control_plane_lease_service.require_active_authority(
                card_id=card_id,
                error_context=f"gitea-state worker renew preflight:{card_id}",
            )
        except ValueError:
            return True
        return False

    async def _publish_expired_lease_if_enabled(
        self,
        *,
        card_id: str,
        lease_observation: Any,
        reason: str,
    ) -> None:
        if self.control_plane_lease_service is None or not isinstance(lease_observation, dict):
            return
        latest = await self.control_plane_lease_service.publication.repository.get_latest_lease_record(
            lease_id=self.control_plane_lease_service.lease_id_for(card_id)
        )
        if latest is not None and latest.status.value == "lease_expired" and await self._latest_resource_matches_lease(
            card_id=card_id,
            lease=latest,
        ):
            return
        await self.control_plane_lease_service.publish_expired_lease(
            card_id=card_id,
            worker_id=self.worker_id,
            lease_observation=lease_observation,
            reason=reason,
        )

    async def _publish_released_lease_if_enabled(
        self,
        *,
        card_id: str,
        lease_observation: Any,
        final_state: str,
    ) -> None:
        if self.control_plane_lease_service is None or not isinstance(lease_observation, dict):
            return
        latest = await self.control_plane_lease_service.publication.repository.get_latest_lease_record(
            lease_id=self.control_plane_lease_service.lease_id_for(card_id)
        )
        if latest is not None and latest.status.value == "lease_released" and await self._latest_resource_matches_lease(
            card_id=card_id,
            lease=latest,
        ):
            return
        await self.control_plane_lease_service.publish_released_lease(
            card_id=card_id,
            worker_id=self.worker_id,
            lease_observation=lease_observation,
            final_state=final_state,
        )

    async def _latest_resource_matches_lease(self, *, card_id: str, lease: Any) -> bool:
        if self.control_plane_lease_service is None:
            return False
        latest_resource = await self.control_plane_lease_service.publication.repository.get_latest_resource_record(
            resource_id=self.control_plane_lease_service.resource_id_for(card_id)
        )
        try:
            require_resource_snapshot_matches_lease(
                resource=latest_resource,
                lease=lease,
                expected_resource_kind="gitea_card",
                expected_namespace_scope=GiteaStateControlPlaneExecutionService.namespace_scope_for(card_id=card_id),
                error_context=f"gitea-state worker card {card_id}",
                error_factory=ValueError,
            )
        except ValueError:
            return False
        return True

    async def _begin_claimed_execution_if_enabled(
        self,
        *,
        card_id: str,
        card: dict[str, Any],
        lease_observation: Any,
    ):
        if self.control_plane_execution_service is None or not isinstance(lease_observation, dict):
            return None, None
        return await self.control_plane_execution_service.begin_claimed_execution(
            card_id=card_id,
            worker_id=self.worker_id,
            from_state=str(card.get("state") or "ready"),
            success_state=self.success_state,
            failure_state=self.failure_state,
            lease_observation=lease_observation,
        )

    async def _publish_claim_transition_if_enabled(
        self,
        *,
        card_id: str,
        from_state: str,
        control_plane_run_id: str | None,
        control_plane_attempt_id: str | None,
    ) -> None:
        if (
            self.control_plane_execution_service is None
            or control_plane_run_id is None
            or control_plane_attempt_id is None
        ):
            return
        await self.control_plane_execution_service.publish_claim_transition(
            run_id=control_plane_run_id,
            attempt_id=control_plane_attempt_id,
            card_id=card_id,
            from_state=from_state,
            to_state="in_progress",
        )

    async def _publish_release_transition_if_enabled(
        self,
        *,
        card_id: str,
        final_state: str,
        error: str | None,
        control_plane_run_id: str | None,
        control_plane_attempt_id: str | None,
    ) -> None:
        if (
            self.control_plane_execution_service is None
            or control_plane_run_id is None
            or control_plane_attempt_id is None
        ):
            return
        await self.control_plane_execution_service.publish_release_transition_and_finalize(
            run_id=control_plane_run_id,
            attempt_id=control_plane_attempt_id,
            card_id=card_id,
            final_state=final_state,
            error=error,
            success_state=self.success_state,
        )

    async def _publish_pre_effect_checkpoint_if_enabled(
        self,
        *,
        card_id: str,
        card: dict[str, Any],
        lease_observation: Any,
        run,
        attempt,
    ) -> None:
        if (
            self.control_plane_checkpoint_service is None
            or run is None
            or attempt is None
            or not isinstance(lease_observation, dict)
        ):
            return
        await self.control_plane_checkpoint_service.publish_pre_effect_checkpoint(
            run=run,
            attempt=attempt,
            card_id=card_id,
            from_state=str(card.get("state") or "ready"),
            lease_observation=lease_observation,
        )
