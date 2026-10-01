"""Own API graph construction and acquired-resource cleanup before runtime admission."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import run_owned_diagnostic, run_owned_io, run_owned_thread
from orket.adapters.observability.logging_context import bind_logging, prepare_logging_native, select_logging_inputs
from orket.application.services.api_runtime_composition import build_api_runtime_container
from orket.application.services.api_runtime_container import ApiRuntimeContainer
from orket.application.services.application_runtime_lifetime import close_owned_resource
from orket.application.services.outbound_policy_input_service import capture_api_outbound_policy
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts.outbound_policy import OutboundPolicyInputs

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class PreparedApiRuntime:
    container: ApiRuntimeContainer
    outbound_policy: OutboundPolicyInputs


class ApiRuntimePreparation:
    def __init__(self, project_root: Path, *, inputs: RuntimeConstructionInputs,
                 runtime_inputs: RuntimeInputService | None = None) -> None:
        self.project_root = inputs.invocation_root / project_root
        self.inputs, self.runtime_inputs = inputs, runtime_inputs
        self._started = False

    @asynccontextmanager
    async def open(self) -> AsyncIterator[PreparedApiRuntime]:
        diagnose = LOGGER.error
        if self._started:
            raise RuntimeError("E_API_RESTART_REQUIRES_NEW_APP")
        self._started = True
        acquired: list[Any] = []
        completed: list[ApiRuntimeContainer] = []
        logging_inputs = select_logging_inputs(self.inputs.invocation_root, self.inputs.environment)
        logging_contexts = []

        def construct() -> PreparedApiRuntime:
            self.inputs.bind_settings()
            logging_context = prepare_logging_native(logging_inputs)
            logging_contexts.append(logging_context)
            with bind_logging(logging_context):
                container = build_api_runtime_container(self.project_root, runtime_inputs=self.runtime_inputs,
                    construction_inputs=self.inputs, own_resource=acquired.append, logging_context=logging_context)
            # Capture the completed owner before another preparation step can fail.
            completed.append(container)
            policy = capture_api_outbound_policy(container.project_root, self.inputs.environment)
            return PreparedApiRuntime(container, policy)

        async def cleanup() -> None:
            owners = [completed[0]] if completed else list(reversed(acquired))
            if logging_contexts:
                with bind_logging(logging_contexts[0]):
                    await _close_acquired(owners, diagnose)

        failure: BaseException | None = None
        try:
            prepared = await run_owned_thread(construct, label="api-runtime-construction")
            yield prepared
        except BaseException as exc:
            # This lifespan boundary retains the original outcome through later cleanup cancellation.
            failure = exc
            if not isinstance(exc, asyncio.CancelledError):
                await run_owned_diagnostic(partial(diagnose, "API preparation or lifespan failed",
                    exc_info=(type(exc), exc, exc.__traceback__)), primary=exc)
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


async def _close_acquired(resources: list[Any], diagnose) -> None:
    errors: list[BaseException] = []
    for resource in resources:
        try:
            await close_owned_resource(resource)
        except (Exception, asyncio.CancelledError) as exc:
            # This construction supervisor must attempt every acquired resource's teardown.
            errors.append(exc)
            await run_owned_diagnostic(partial(diagnose, "API construction resource cleanup failed (%s)",
                type(resource).__name__, exc_info=(type(exc), exc, exc.__traceback__)), primary=exc)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("API construction resource cleanup failed", errors)
