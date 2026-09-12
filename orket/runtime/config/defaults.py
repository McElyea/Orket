from __future__ import annotations

import os

# Shared defaults for runtime, workload, and provider-neutral tooling entrypoints.
DEFAULT_LOCAL_PROVIDER: str = "llama_cpp"
DEFAULT_LOCAL_MODEL: str = "orcarouter_qwen3.8-27b-uncensored-q4_k_l"


def configured_provider(*keys: str) -> str:
    """Resolve explicit provider settings, ignoring blank values, then the default."""
    for key in keys or ("ORKET_LLM_PROVIDER", "ORKET_MODEL_PROVIDER"):
        value = str(os.getenv(key) or "").strip().lower()
        if value:
            return value
    return DEFAULT_LOCAL_PROVIDER
