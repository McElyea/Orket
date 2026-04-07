from __future__ import annotations

import os
from typing import Any


def parse_quarantined_providers(value: Any) -> set[str]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    tokens = {str(token).strip().lower() for token in raw.split(",") if str(token).strip()}
    return tokens


def parse_quarantined_provider_models(value: Any) -> set[tuple[str, str]]:
    raw = str(value or "").strip()
    if not raw:
        return set()
    rows: set[tuple[str, str]] = set()
    for token in raw.split(","):
        entry = str(token or "").strip()
        if ":" not in entry:
            continue
        provider, model = entry.split(":", 1)
        provider_token = str(provider or "").strip().lower()
        model_token = str(model or "").strip()
        if provider_token and model_token:
            rows.add((provider_token, model_token))
    return rows


def resolve_provider_quarantine_policy(
    *,
    environment: dict[str, str] | None = None,
) -> dict[str, object]:
    env = environment if isinstance(environment, dict) else dict(os.environ)
    providers = parse_quarantined_providers(env.get("ORKET_PROVIDER_QUARANTINE"))
    provider_models = parse_quarantined_provider_models(env.get("ORKET_PROVIDER_MODEL_QUARANTINE"))
    return {
        "providers": sorted(providers),
        "provider_models": sorted(provider_models),
    }


def is_provider_quarantined(
    *,
    requested_provider: str,
    canonical_provider: str,
    quarantined_providers: set[str],
) -> bool:
    requested = str(requested_provider or "").strip().lower()
    canonical = str(canonical_provider or "").strip().lower()
    return requested in quarantined_providers or canonical in quarantined_providers


def is_model_quarantined(
    *,
    requested_provider: str,
    canonical_provider: str,
    model_id: str,
    quarantined_provider_models: set[tuple[str, str]],
) -> bool:
    model = str(model_id or "").strip()
    if not model:
        return False
    requested = str(requested_provider or "").strip().lower()
    canonical = str(canonical_provider or "").strip().lower()
    return (requested, model) in quarantined_provider_models or (canonical, model) in quarantined_provider_models
