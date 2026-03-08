from __future__ import annotations

from typing import Any

import httpx

from orket.exceptions import ModelConnectionError
from orket.runtime.provider_runtime_target import (
    ProviderRuntimeWarmupError,
    resolve_bool_env,
    resolve_float_env,
    resolve_int_env,
    resolve_provider_runtime_target,
)


def uses_runtime_managed_client(*, provider_backend: str, client: Any) -> bool:
    if provider_backend == "openai_compat":
        return (
            client is not None
            and str(client.__class__.__name__ or "") == "AsyncClient"
            and str(client.__class__.__module__ or "").startswith("httpx")
        )
    return bool(client) and str(client.__class__.__module__ or "").startswith("ollama")


async def ensure_provider_runtime_target(provider: Any) -> str:
    if getattr(provider, "_runtime_target", None) is not None:
        return str(provider.model)
    if not uses_runtime_managed_client(
        provider_backend=str(provider.provider_backend),
        client=getattr(provider, "client", None),
    ):
        return str(provider.model)
    try:
        target = await resolve_provider_runtime_target(
            provider=str(provider.provider_name),
            requested_model=str(provider.requested_model),
            base_url=provider.openai_base_url if provider.provider_backend == "openai_compat" else provider.ollama_host,
            timeout_s=max(1.0, float(provider.timeout)),
            auto_select_model=resolve_bool_env(
                "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL",
                "ORKET_LLM_AUTO_SELECT_MODEL",
                default=True,
            ),
            auto_load_local_model=resolve_bool_env(
                "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL",
                "ORKET_LLM_AUTO_LOAD_LOCAL_MODEL",
                default=True,
            ),
            model_load_timeout_s=resolve_float_env("ORKET_PROVIDER_RUNTIME_MODEL_LOAD_TIMEOUT_SEC", default=180.0),
            model_ttl_sec=resolve_int_env("ORKET_PROVIDER_RUNTIME_MODEL_TTL_SEC", default=600),
            api_key=getattr(provider, "openai_api_key", "") or None,
        )
    except (ProviderRuntimeWarmupError, httpx.HTTPError) as exc:
        raise ModelConnectionError(
            "Provider runtime preparation failed "
            f"provider={provider.provider_name} requested_model={provider.requested_model or '(unset)'}: {exc}"
        ) from exc
    provider._runtime_target = target
    if not str(target.model_id or "").strip():
        available = ", ".join(target.available_models[:12]) or "(no models discovered)"
        raise ModelConnectionError(
            "Provider runtime target resolution failed "
            f"provider={target.requested_provider} requested_model={provider.requested_model or '(unset)'} "
            f"resolution_mode={target.resolution_mode} available={available}"
        )
    provider.model = str(target.model_id)
    if provider.provider_backend == "openai_compat":
        provider.openai_base_url = str(target.base_url)
    else:
        provider.ollama_host = str(target.base_url)
    return str(provider.model)


def provider_runtime_target_payload(provider: Any) -> dict[str, Any] | None:
    target = getattr(provider, "_runtime_target", None)
    return target.to_payload() if target is not None else None
