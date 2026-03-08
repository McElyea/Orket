from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orket.runtime.provider_runtime_target import (
    ProviderRuntimeWarmupError,
    resolve_provider_runtime_target_sync,
)


def warmup_provider_model(
    *,
    provider: str,
    requested_model: str,
    base_url: str | None,
    timeout_s: float,
    auto_select_model: bool,
    auto_load_local_model: bool,
    model_load_timeout_s: float,
    model_ttl_sec: int,
) -> dict[str, Any]:
    payload = dict(
        resolve_provider_runtime_target_sync(
            provider=provider,
            requested_model=requested_model,
            base_url=base_url,
            timeout_s=timeout_s,
            auto_select_model=auto_select_model,
            auto_load_local_model=auto_load_local_model,
            model_load_timeout_s=model_load_timeout_s,
            model_ttl_sec=model_ttl_sec,
        )
    )
    payload.setdefault("resolved_model", str(payload.get("model_id") or ""))
    return payload
