"""Shared inventory for synchronous discovery entrypoints."""
from __future__ import annotations

import httpx

from orket.logging import log_event
from orket.runtime.config.defaults import configured_provider
from orket.runtime.config.provider_runtime_inventory import _run_coro_sync
from orket.runtime.config.provider_runtime_target import ProviderRuntimeWarmupError, list_provider_models


def installed_models() -> list[str]:
    """Use the selected provider only; a failed inventory never switches providers."""
    provider = configured_provider()
    try:
        payload = _run_coro_sync(list_provider_models(provider=provider, base_url=None, timeout_s=5.0))
    except (httpx.HTTPError, OSError, ValueError, ProviderRuntimeWarmupError) as exc:
        log_event("provider_discovery_failed", {"provider": provider, "error_type": type(exc).__name__})
        return []
    return [str(model) for model in payload["models"]]
