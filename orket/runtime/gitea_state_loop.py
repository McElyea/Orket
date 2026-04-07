from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.gitea_state_control_plane_checkpoint_service import (
    build_gitea_state_control_plane_checkpoint_service,
)
from orket.application.services.gitea_state_control_plane_execution_service import (
    build_gitea_state_control_plane_execution_service,
)
from orket.application.services.gitea_state_control_plane_lease_service import (
    build_gitea_state_control_plane_lease_service,
)
from orket.application.services.gitea_state_control_plane_reservation_service import (
    build_gitea_state_control_plane_reservation_service,
)
from orket.application.services.gitea_state_pilot import (
    collect_gitea_state_pilot_inputs,
    evaluate_gitea_state_pilot_readiness,
)
from orket.application.services.gitea_state_worker import GiteaStateWorker
from orket.application.services.gitea_state_worker_coordinator import GiteaStateWorkerCoordinator
from orket.application.services.runtime_policy import (
    resolve_gitea_worker_max_duration_seconds,
    resolve_gitea_worker_max_idle_streak,
    resolve_gitea_worker_max_iterations,
)
from orket.runtime.settings import resolve_str
from orket.runtime_paths import resolve_control_plane_db_path
from orket.settings import load_user_settings_async

RunCardCallback = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True)
class GiteaStateLoopRunner:
    state_backend_mode: str
    organization: Any
    run_card: RunCardCallback

    async def run(
        self,
        *,
        worker_id: str,
        fetch_limit: int = 5,
        lease_seconds: int = 30,
        renew_interval_seconds: float = 5.0,
        max_iterations: int | None = None,
        max_idle_streak: int | None = None,
        max_duration_seconds: float | None = None,
        idle_sleep_seconds: float = 0.0,
        summary_out: str | Path | None = None,
    ) -> dict[str, Any]:
        if self.state_backend_mode != "gitea":
            raise ValueError("run_gitea_state_loop requires state_backend_mode='gitea'")
        inputs = self._collect_ready_inputs()
        limits = await self._resolve_limits(
            max_iterations=max_iterations,
            max_idle_streak=max_idle_streak,
            max_duration_seconds=max_duration_seconds,
        )
        worker = self._build_worker(
            inputs=inputs,
            worker_id=worker_id,
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
        )
        coordinator = GiteaStateWorkerCoordinator(
            worker=worker,
            fetch_limit=fetch_limit,
            max_iterations=limits["max_iterations"],
            max_idle_streak=limits["max_idle_streak"],
            max_duration_seconds=limits["max_duration_seconds"],
            idle_sleep_seconds=idle_sleep_seconds,
        )
        summary = await coordinator.run(work_fn=self._work_claimed_card, summary_out=summary_out)
        return {
            "worker_id": str(worker_id),
            "fetch_limit": max(1, int(fetch_limit)),
            **limits,
            "summary": summary,
        }

    def _collect_ready_inputs(self) -> dict[str, Any]:
        inputs = collect_gitea_state_pilot_inputs()
        readiness = evaluate_gitea_state_pilot_readiness(inputs)
        if bool(readiness.get("ready")):
            return inputs
        failures = ", ".join(list(readiness.get("failures") or [])) or "unknown readiness failure"
        raise RuntimeError(f"State backend mode 'gitea' pilot readiness failed: {failures}")

    async def _resolve_limits(
        self,
        *,
        max_iterations: int | None,
        max_idle_streak: int | None,
        max_duration_seconds: float | None,
    ) -> dict[str, Any]:
        raw_user_settings = await load_user_settings_async()
        user_settings = raw_user_settings if isinstance(raw_user_settings, dict) else {}
        return {
            "max_iterations": int(
                resolve_gitea_worker_max_iterations(
                    max_iterations,
                    resolve_str("ORKET_GITEA_WORKER_MAX_ITERATIONS"),
                    self._process_rule("gitea_worker_max_iterations"),
                    user_settings.get("gitea_worker_max_iterations"),
                )
            ),
            "max_idle_streak": int(
                resolve_gitea_worker_max_idle_streak(
                    max_idle_streak,
                    resolve_str("ORKET_GITEA_WORKER_MAX_IDLE_STREAK"),
                    self._process_rule("gitea_worker_max_idle_streak"),
                    user_settings.get("gitea_worker_max_idle_streak"),
                )
            ),
            "max_duration_seconds": float(
                resolve_gitea_worker_max_duration_seconds(
                    max_duration_seconds,
                    resolve_str("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS"),
                    self._process_rule("gitea_worker_max_duration_seconds"),
                    user_settings.get("gitea_worker_max_duration_seconds"),
                )
            ),
        }

    def _process_rule(self, key: str, default: Any = None) -> Any:
        process_rules = getattr(self.organization, "process_rules", None) if self.organization else None
        if process_rules is None:
            return default
        if isinstance(process_rules, dict):
            return process_rules.get(key, default)
        getter = getattr(process_rules, "get", None)
        if callable(getter):
            return getter(key, default)
        return getattr(process_rules, key, default)

    @staticmethod
    def _build_worker(
        *,
        inputs: dict[str, Any],
        worker_id: str,
        lease_seconds: int,
        renew_interval_seconds: float,
    ) -> GiteaStateWorker:
        control_plane_db_path = resolve_control_plane_db_path()
        adapter = GiteaStateAdapter(
            base_url=str(inputs.get("gitea_url") or ""),
            token=str(inputs.get("gitea_token") or ""),
            owner=str(inputs.get("gitea_owner") or ""),
            repo=str(inputs.get("gitea_repo") or ""),
        )
        return GiteaStateWorker(
            adapter=adapter,
            worker_id=str(worker_id),
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
            control_plane_checkpoint_service=build_gitea_state_control_plane_checkpoint_service(
                control_plane_db_path
            ),
            control_plane_execution_service=build_gitea_state_control_plane_execution_service(control_plane_db_path),
            control_plane_lease_service=build_gitea_state_control_plane_lease_service(control_plane_db_path),
            control_plane_reservation_service=build_gitea_state_control_plane_reservation_service(
                control_plane_db_path
            ),
        )

    async def _work_claimed_card(self, card: dict[str, Any]) -> dict[str, Any]:
        target = str(card.get("card_id") or "").strip()
        if not target:
            raise ValueError("missing card_id in gitea snapshot payload")
        await self.run_card(target)
        return {"card_id": target, "result": "ok"}


async def run_gitea_state_loop(
    *,
    state_backend_mode: str,
    organization: Any,
    run_card: RunCardCallback,
    worker_id: str,
    fetch_limit: int = 5,
    lease_seconds: int = 30,
    renew_interval_seconds: float = 5.0,
    max_iterations: int | None = None,
    max_idle_streak: int | None = None,
    max_duration_seconds: float | None = None,
    idle_sleep_seconds: float = 0.0,
    summary_out: str | Path | None = None,
) -> dict[str, Any]:
    return await GiteaStateLoopRunner(
        state_backend_mode=state_backend_mode,
        organization=organization,
        run_card=run_card,
    ).run(
        worker_id=worker_id,
        fetch_limit=fetch_limit,
        lease_seconds=lease_seconds,
        renew_interval_seconds=renew_interval_seconds,
        max_iterations=max_iterations,
        max_idle_streak=max_idle_streak,
        max_duration_seconds=max_duration_seconds,
        idle_sleep_seconds=idle_sleep_seconds,
        summary_out=summary_out,
    )
