"""Provider evidence shared by direct and API streaming scenarios."""
from __future__ import annotations

import os
from typing import Any

from orket.runtime.config.provider_runtime_target import default_base_url, normalize_base_url, normalize_provider
from orket.runtime.defaults import DEFAULT_LOCAL_MODEL


def provider_identity(*, resolved_model_id: str = "") -> dict[str, Any]:
    mode = str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()
    provider = str(os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama") or "ollama").strip().lower()
    model = str(resolved_model_id or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", DEFAULT_LOCAL_MODEL)).strip()
    canonical = normalize_provider(provider)
    base_url = default_base_url(provider)
    if provider in {"openai_compat", "lmstudio"}:
        base_url = os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", base_url)
    base_url = normalize_base_url(base_url, default=default_base_url(provider))
    streaming = canonical == "ollama" or str(os.getenv("ORKET_MODEL_STREAM_OPENAI_USE_STREAM", "false")).lower() in {
        "1", "true", "yes", "on",
    }
    live = mode == "real"
    return {
        "provider_mode": mode,
        "provider": provider if live else "stub",
        "provider_name": provider if live else "stub",
        "canonical_provider": canonical if live else "stub",
        "base_url": base_url if live else None,
        "provider_base_url": base_url if live else None,
        "model_id": model if live else None,
        "provider_model_id": model if live else None,
        "streaming": live and streaming,
        "openai_compat": live and canonical == "openai_compat",
    }
