from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.core.contracts.provider_runtime import (  # noqa: E402
    DEFAULT_LOCAL_PROVIDER,  # noqa: E402 - direct script bootstrap
    effective_provider,
    normalize_provider,
)
from orket.core.contracts.provider_runtime import PROVIDER_CHOICES as PROVIDER_CHOICES  # noqa: E402
from orket.runtime.provider_runtime_target import (  # noqa: E402 - repository path bootstrap
    _list_ollama_models_sync as _runtime_list_ollama_models,
)
from orket.runtime.provider_runtime_target import (  # noqa: E402 - repository path bootstrap
    _list_openai_compat_models_sync as _runtime_list_openai_compat_models,
)
from orket.runtime.provider_runtime_target import (  # noqa: E402
    choose_model as choose_model,
)
from orket.runtime.provider_runtime_target import (  # noqa: E402 - direct script bootstrap
    default_base_url,
    normalize_base_url,
)
from orket.runtime.provider_runtime_target import (  # noqa: E402 - direct script bootstrap
    rank_models as rank_models,
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
    requested = effective_provider(provider, default=DEFAULT_LOCAL_PROVIDER)
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
