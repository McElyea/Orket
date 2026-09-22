"""Application authority for provider discovery, selection, loading and admission."""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import httpx

from orket.application.services.process_input_service import capture_process_context
from orket.core.contracts.provider_preparation import ProviderPreparationRequest
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget
from orket.exceptions import ModelConnectionError
from orket.runtime.config.provider_runtime_target import (
    ProviderRuntimeWarmupError,
    resolve_bool_env,
    resolve_float_env,
    resolve_int_env,
    resolve_provider_runtime_target,
)


class ProviderPreparationService:
    def __init__(self, *, environment: Mapping[str, str], cwd: Path | None = None) -> None:
        self._cwd, self._environment = capture_process_context(cwd=cwd, environment=environment)

    async def prepare(self, request: ProviderPreparationRequest) -> ProviderRuntimeTarget:
        environment = self._environment
        try:
            return await resolve_provider_runtime_target(
                provider=request.provider, requested_model=request.requested_model, base_url=request.base_url,
                timeout_s=request.timeout_s,
                auto_select_model=resolve_bool_env(
                    "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL", "ORKET_LLM_AUTO_SELECT_MODEL",
                    default=True, environment=environment,
                ),
                auto_load_local_model=resolve_bool_env(
                    "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL", "ORKET_LLM_AUTO_LOAD_LOCAL_MODEL",
                    default=True, environment=environment,
                ),
                model_load_timeout_s=resolve_float_env(
                    "ORKET_PROVIDER_RUNTIME_MODEL_LOAD_TIMEOUT_SEC", default=180.0, environment=environment),
                model_ttl_sec=resolve_int_env(
                    "ORKET_PROVIDER_RUNTIME_MODEL_TTL_SEC", default=600, environment=environment),
                api_key=request.api_key or None, environment=environment, cwd=self._cwd,
            )
        except (ProviderRuntimeWarmupError, httpx.HTTPError) as exc:
            raise ModelConnectionError(
                "Provider runtime preparation failed "
                f"provider={request.provider} requested_model={request.requested_model or '(unset)'}: {exc}"
            ) from exc
