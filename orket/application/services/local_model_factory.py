"""Application composition binds captured settings and prompt authority to transport."""
from __future__ import annotations

import logging
from collections.abc import Mapping
from functools import partial
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_prompting_service import LocalPromptingService
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.provider_inference_http_service import ProviderInferenceHttpService
from orket.application.services.provider_preparation_service import ProviderPreparationService
from orket.application.services.runtime_result_lifetime import create_runtime_owner
from orket.capabilities.sync_bridge import run_coro_sync
from orket.core.contracts.provider_http import ProviderInferenceHttpPort
from orket.core.contracts.provider_preparation import ProviderPreparationPort

LOGGER = logging.getLogger(__name__)


def create_local_model_provider(*args: Any, environment: Mapping[str, str] | None = None,
                                runtime_preparation: ProviderPreparationPort | None = None,
                                cwd: Path | None = None, http_client_owner: ProviderInferenceHttpPort | None = None,
                                **kwargs: Any) -> LocalModelProvider:
    require_sync_context(code="E_PROVIDER_FACTORY_REQUIRES_ASYNC_OWNER")
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    owner = http_client_owner if http_client_owner is not None else ProviderInferenceHttpService(
        environment=captured, cwd=directory)
    try:
        return LocalModelProvider(*args, environment=captured, http_client_owner=owner,
            prompt_policy=LocalPromptingService(environment=captured),
            runtime_preparation=(runtime_preparation if runtime_preparation is not None
                                 else ProviderPreparationService(environment=captured, cwd=directory)), **kwargs)
    except BaseException as failure:
        # Native construction supervisor owns partial acquisition before a provider exists.
        LOGGER.error("Native provider construction failed (%s)", type(failure).__name__)
        try:
            run_coro_sync(owner.close())
        except BaseException as cleanup_failure:
            raise BaseExceptionGroup("Provider construction and cleanup failed", [failure, cleanup_failure]) from None
        raise


async def create_local_model_provider_async(*args: Any, environment: Mapping[str, str] | None = None,
                                          cwd: Path | None = None, **kwargs: Any) -> LocalModelProvider:
    directory, captured = capture_process_context(cwd=cwd, environment=environment)
    return await create_runtime_owner(partial(create_local_model_provider, *args,
        environment=captured, cwd=directory, **kwargs), label="provider-client-construction")
