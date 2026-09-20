"""Own API graph construction and acquired-resource cleanup before runtime admission."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_io, run_owned_thread
from orket.application.services.api_runtime_composition import build_api_runtime_container
from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.application.services.application_runtime_lifetime import close_owned_resource
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.kernel.v1.outbound_policy_gate import load_outbound_policy_config_file

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedApiRuntime:
    container: ApiRuntimeContainer
    outbound_policy: dict[str, Any]


class ApiRuntimePreparation:
    def __init__(self, project_root: Path, *, inputs: RuntimeConstructionInputs,
                 runtime_inputs: RuntimeInputService | None = None) -> None:
        self.project_root = inputs.invocation_root / project_root
        self.inputs, self.runtime_inputs = inputs, runtime_inputs
        self._started = False

    @asynccontextmanager
    async def open(self) -> AsyncIterator[PreparedApiRuntime]:
        if self._started:
            raise RuntimeError("E_API_RESTART_REQUIRES_NEW_APP")
        self._started = True
        acquired: list[Any] = []
        completed: list[PreparedApiRuntime] = []

        def construct() -> PreparedApiRuntime:
            self.inputs.bind_settings()
            container = build_api_runtime_container(self.project_root, runtime_inputs=self.runtime_inputs,
                construction_inputs=self.inputs, own_resource=acquired.append)
            # Capture the completed owner before another preparation step can fail.
            prepared = PreparedApiRuntime(container, {})
            completed.append(prepared)
            prepared.outbound_policy.update(_outbound_policy(container.project_root, self.inputs))
            return prepared

        async def cleanup() -> None:
            owners = [completed[0].container] if completed else list(reversed(acquired))
            await _close_acquired(owners)

        failure: BaseException | None = None
        try:
            prepared = await run_owned_thread(construct, label="api-runtime-construction")
            yield prepared
        except BaseException as exc:
            # This lifespan boundary retains the original outcome through later cleanup cancellation.
            failure = exc
            if not isinstance(exc, asyncio.CancelledError):
                LOGGER.error("API preparation or lifespan failed", exc_info=True)
        try:
            await run_owned_io(cleanup, label="api-construction-cleanup", preserve_failure=True)
        except asyncio.CancelledError:
            if failure is None:
                raise
        except BaseException as cleanup_failure:
            if failure is not None and cleanup_failure is not failure:
                raise BaseExceptionGroup("API preparation and cleanup failed", [failure, cleanup_failure]) from None
            raise
        if failure is not None:
            raise failure


def build_api_runtime_preparation(project_root: Path, *, inputs: RuntimeConstructionInputs,
                                  runtime_inputs: RuntimeInputService | None = None) -> ApiRuntimePreparation:
    return ApiRuntimePreparation(project_root, inputs=inputs, runtime_inputs=runtime_inputs)


def _outbound_policy(project_root: Path, inputs: RuntimeConstructionInputs) -> dict[str, Any]:
    raw = str(inputs.environment.get("ORKET_OUTBOUND_POLICY_CONFIG_PATH") or "").strip()
    return dict(load_outbound_policy_config_file(project_root / raw)) if raw else {}


async def _close_acquired(resources: list[Any]) -> None:
    errors: list[BaseException] = []
    for resource in resources:
        try:
            await close_owned_resource(resource)
        except (Exception, asyncio.CancelledError) as exc:
            # This construction supervisor must attempt every acquired resource's teardown.
            LOGGER.error("API construction resource cleanup failed (%s)", type(resource).__name__, exc_info=True)
            errors.append(exc)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("API construction resource cleanup failed", errors)
