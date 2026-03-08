from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.provider_runtime_target import (
    PROVIDER_CHOICES,
    _list_ollama_models_sync as _runtime_list_ollama_models,
    _list_openai_compat_models_sync as _runtime_list_openai_compat_models,
    choose_model,
    default_base_url,
    effective_provider,
    normalize_base_url,
    normalize_provider,
    rank_models,
)


def _list_openai_compat_models(*, base_url: str, api_key: str | None, timeout_s: float) -> list[str]:
    return list(_runtime_list_openai_compat_models(base_url=base_url, api_key=api_key, timeout_s=timeout_s))


def _list_ollama_models(*, base_url: str, timeout_s: float) -> list[str]:
    return list(_runtime_list_ollama_models(base_url=base_url, timeout_s=timeout_s))


def list_provider_models(
    *,
    provider: str,
    base_url: str | None,
    timeout_s: float,
    api_key: str | None = None,
) -> dict[str, object]:
    requested = effective_provider(provider, default="ollama")
    canonical = normalize_provider(requested)
    resolved_base_url = normalize_base_url(base_url, default=default_base_url(requested))
    if canonical == "openai_compat":
        models = _list_openai_compat_models(base_url=resolved_base_url, api_key=api_key, timeout_s=timeout_s)
    else:
        models = _list_ollama_models(base_url=resolved_base_url, timeout_s=timeout_s)
    return {
        "requested_provider": requested,
        "canonical_provider": canonical,
        "base_url": resolved_base_url,
        "models": list(models),
    }
