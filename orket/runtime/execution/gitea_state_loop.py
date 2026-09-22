from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from types import MappingProxyType
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.adapters.storage.gitea_state_adapter import GiteaStateAdapter
from orket.application.services.application_runtime_lifetime import close_owned_resource
from orket.application.services.gitea_state_adapter_factory import create_gitea_state_adapter
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
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.services.runtime_policy import (
    resolve_gitea_worker_max_duration_seconds,
    resolve_gitea_worker_max_idle_streak,
    resolve_gitea_worker_max_iterations,
)
from orket.application.services.runtime_result_projection import require_runtime_success
from orket.orchestration.orchestration_config import Organization, process_rule_value
from orket.runtime_paths import resolve_control_plane_db_path
from orket.settings import load_user_settings_async

RunCardCallback = Callable[[str], Awaitable[Any]]
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class GiteaStateLoopRunner:
    state_backend_mode: str
    organization: Organization | None
    run_card: RunCardCallback
    construction_inputs: RuntimeConstructionInputs | None = field(default=None, repr=False)
    runtime_inputs: RuntimeInputService = field(default_factory=RuntimeInputService, repr=False)
    control_plane_db_path: Path | None = None
    _environment: Mapping[str, str] = field(init=False, repr=False)
    _invocation_root: Path = field(init=False)
    _rule_tokens: tuple[str, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if self.state_backend_mode != "gitea":
            raise ValueError("run_gitea_state_loop requires state_backend_mode='gitea'")
        supplied = self.construction_inputs
        root = supplied.invocation_root if supplied is not None else Path.cwd()
        environment = dict(supplied.environment if supplied is not None else os.environ)
        object.__setattr__(self, "_invocation_root", root)
        object.__setattr__(self, "_environment", MappingProxyType(environment))
        object.__setattr__(self, "_rule_tokens", tuple(str(process_rule_value(self.organization, key, None) or "").strip()
            for key in ("gitea_worker_max_iterations", "gitea_worker_max_idle_streak", "gitea_worker_max_duration_seconds")))
        if self.control_plane_db_path is not None:
            object.__setattr__(self, "control_plane_db_path", root / self.control_plane_db_path)

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
        inputs = self._collect_ready_inputs()
        selected_worker = str(worker_id)
        selected_fetch, selected_lease = max(1, int(fetch_limit)), max(1, int(lease_seconds))
        selected_renew, selected_idle = max(0.1, float(renew_interval_seconds)), max(0.0, float(idle_sleep_seconds))
        summary_path = self._invocation_root / summary_out if summary_out is not None else None
        limits = await self._resolve_limits(
            max_iterations=max_iterations,
            max_idle_streak=max_idle_streak,
            max_duration_seconds=max_duration_seconds,
        )
        construct = partial(self._build_worker,
            inputs=inputs,
            worker_id=selected_worker,
            lease_seconds=selected_lease,
            renew_interval_seconds=selected_renew,
        )
        async with _owned_worker(construct) as worker:
            coordinator = GiteaStateWorkerCoordinator(
                worker=worker,
                fetch_limit=selected_fetch,
                max_iterations=limits["max_iterations"],
                max_idle_streak=limits["max_idle_streak"],
                max_duration_seconds=limits["max_duration_seconds"],
                idle_sleep_seconds=selected_idle,
                runtime_inputs=self.runtime_inputs,
            )
            summary = await coordinator.run(work_fn=self._work_claimed_card, summary_out=summary_path)
        return {
            "worker_id": selected_worker,
            "fetch_limit": selected_fetch,
            **limits,
            "summary": summary,
        }

    def _collect_ready_inputs(self) -> dict[str, Any]:
        inputs = collect_gitea_state_pilot_inputs(environment=self._environment)
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
        explicit = tuple(str(value or "").strip() for value in (max_iterations, max_idle_streak, max_duration_seconds))
        supplied = self.construction_inputs
        raw_user_settings = supplied.user_settings() if supplied is not None else await load_user_settings_async()
        user_settings = raw_user_settings if isinstance(raw_user_settings, dict) else {}
        return {
            "max_iterations": int(
                resolve_gitea_worker_max_iterations(
                    explicit[0],
                    self._environment.get("ORKET_GITEA_WORKER_MAX_ITERATIONS"),
                    self._rule_tokens[0],
                    user_settings.get("gitea_worker_max_iterations"),
                )
            ),
            "max_idle_streak": int(
                resolve_gitea_worker_max_idle_streak(
                    explicit[1],
                    self._environment.get("ORKET_GITEA_WORKER_MAX_IDLE_STREAK"),
                    self._rule_tokens[1],
                    user_settings.get("gitea_worker_max_idle_streak"),
                )
            ),
            "max_duration_seconds": float(
                resolve_gitea_worker_max_duration_seconds(
                    explicit[2],
                    self._environment.get("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS"),
                    self._rule_tokens[2],
                    user_settings.get("gitea_worker_max_duration_seconds"),
                )
            ),
        }

    def _build_worker(
        self,
        *,
        inputs: dict[str, Any],
        worker_id: str,
        lease_seconds: int,
        renew_interval_seconds: float,
        own_adapter: Callable[[GiteaStateAdapter], None],
    ) -> GiteaStateWorker:
        control_plane_db_path = resolve_control_plane_db_path(self.control_plane_db_path,
            invocation_root=self._invocation_root, environment=self._environment)
        adapter = create_gitea_state_adapter(
            environment=self._environment, cwd=self._invocation_root,
            base_url=str(inputs.get("gitea_url") or ""),
            token=str(inputs.get("gitea_token") or ""),
            owner=str(inputs.get("gitea_owner") or ""),
            repo=str(inputs.get("gitea_repo") or ""),
        )
        own_adapter(adapter)
        return GiteaStateWorker(
            adapter=adapter,
            worker_id=str(worker_id),
            lease_seconds=lease_seconds,
            renew_interval_seconds=renew_interval_seconds,
            control_plane_checkpoint_service=build_gitea_state_control_plane_checkpoint_service(
                control_plane_db_path
            ),
            control_plane_execution_service=build_gitea_state_control_plane_execution_service(
                control_plane_db_path, now_utc=self.runtime_inputs.utc_now_iso),
            control_plane_lease_service=build_gitea_state_control_plane_lease_service(
                control_plane_db_path, now_utc=self.runtime_inputs.utc_now_iso),
            control_plane_reservation_service=build_gitea_state_control_plane_reservation_service(
                control_plane_db_path, now_utc=self.runtime_inputs.utc_now_iso,
            ),
        )

    async def _work_claimed_card(self, card: dict[str, Any]) -> dict[str, Any]:
        target = str(card.get("card_id") or "").strip()
        if not target:
            raise ValueError("missing card_id in gitea snapshot payload")
        require_runtime_success(await self.run_card(target))
        return {"card_id": target, "result": "ok"}


async def run_gitea_state_loop(
    *,
    state_backend_mode: str,
    organization: Organization | None,
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
    construction_inputs: RuntimeConstructionInputs | None = None,
    runtime_inputs: RuntimeInputService | None = None,
    control_plane_db_path: Path | None = None,
) -> dict[str, Any]:
    return await GiteaStateLoopRunner(
        state_backend_mode=state_backend_mode,
        organization=organization,
        run_card=run_card,
        construction_inputs=construction_inputs,
        runtime_inputs=RuntimeInputService() if runtime_inputs is None else runtime_inputs,
        control_plane_db_path=control_plane_db_path,
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


@asynccontextmanager
async def _owned_worker(construct: Callable[..., GiteaStateWorker]) -> AsyncIterator[GiteaStateWorker]:
    acquired: list[GiteaStateAdapter] = []
    failure: BaseException | None = None
    try:
        worker = await run_owned_thread(partial(construct, own_adapter=acquired.append), label="gitea-worker-construction")
        yield worker
    except BaseException as exc:
        # This loop lifetime boundary retains failure until acquired transport cleanup settles.
        failure = exc
        if not isinstance(exc, asyncio.CancelledError):
            LOGGER.error("Gitea loop preparation or execution failed", exc_info=True)
    try:
        if acquired:
            await run_owned_io(lambda: close_owned_resource(acquired[0]), label="gitea-loop-transport-close", preserve_failure=True)
    except asyncio.CancelledError:
        if failure is None:
            raise
    except BaseException as cleanup_failure:
        LOGGER.error("Gitea loop transport cleanup failed", exc_info=True)
        if failure is not None and cleanup_failure is not failure:
            raise BaseExceptionGroup("Gitea loop and transport cleanup failed", [failure, cleanup_failure]) from None
        raise
    if failure is not None:
        raise failure
