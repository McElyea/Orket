"""Bind application-prepared target values before adapter inference."""
from __future__ import annotations

from typing import Any

from orket.core.contracts.provider_preparation import ProviderPreparationRequest, require_prepared_target
from orket.core.contracts.provider_runtime import DEFAULT_OLLAMA_BASE_URL, ProviderRuntimeTarget

side_effecting = True


async def ensure_provider_runtime_target(provider: Any) -> str:
    if getattr(provider, "_runtime_target", None) is not None:
        return str(provider.model)
    request = ProviderPreparationRequest(
        provider=str(provider.provider_name), requested_model=str(provider.requested_model),
        base_url=(provider.openai_base_url if provider.provider_backend == "openai_compat"
                  else provider.ollama_host or DEFAULT_OLLAMA_BASE_URL),
        timeout_s=max(1.0, float(provider.timeout)), api_key=getattr(provider, "openai_api_key", "") or "",
    )
    target = await provider._runtime_preparation.prepare(request)
    require_prepared_target(request, target)
    provider._runtime_target = target
    provider.model = str(target.model_id)
    if provider.provider_backend == "openai_compat":
        provider.openai_base_url = str(target.base_url)
    else:
        provider.ollama_host = str(target.base_url)
    return str(provider.model)


def provider_runtime_target_payload(provider: Any) -> dict[str, Any] | None:
    target = getattr(provider, "_runtime_target", None)
    return target.to_payload() if target is not None else None


def validate_pinned_runtime_target(provider: Any, target: ProviderRuntimeTarget | None) -> None:
    """Reject mismatched admission before constructing an inference client."""
    if target is None:
        return
    base_url = provider.openai_base_url if provider.provider_backend == "openai_compat" else provider.ollama_host
    if (
        target.status != "OK"
        or target.requested_provider != provider.provider_name
        or target.canonical_provider != provider.provider_backend
        or target.requested_model != provider.requested_model
        or target.model_id != provider.requested_model
        or not target.model_id
        or target.base_url.rstrip("/") != base_url.rstrip("/")
    ):
        raise ValueError("E_PROVIDER_PINNED_TARGET_MISMATCH")
