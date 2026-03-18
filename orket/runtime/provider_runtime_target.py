from __future__ import annotations

import asyncio
import os
import re
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlparse

from orket.runtime.provider_quarantine_policy import (
    is_model_quarantined,
    is_provider_quarantined,
    resolve_provider_quarantine_policy,
)
from orket.runtime.provider_runtime_inventory import (
    ProviderRuntimeWarmupError as _ProviderRuntimeWarmupError,
    _run_coro_sync,
    list_installed_lmstudio_models_sync as _list_installed_lmstudio_models_sync,
    list_installed_ollama_models_sync as _list_installed_ollama_models_sync,
    list_loaded_lmstudio_model_ids_sync as _list_loaded_lmstudio_model_ids_sync,
    list_ollama_models as _list_ollama_models,
    list_ollama_models_sync as _inventory_list_ollama_models_sync,
    list_openai_compat_models as _list_openai_compat_models,
    list_openai_compat_models_sync as _inventory_list_openai_compat_models_sync,
    load_lmstudio_model_sync as _load_lmstudio_model_sync,
)
from orket.runtime.unknown_input_policy import validate_allowed_token

ProviderRuntimeWarmupError = _ProviderRuntimeWarmupError
_list_ollama_models_sync = _inventory_list_ollama_models_sync
_list_openai_compat_models_sync = _inventory_list_openai_compat_models_sync


PROVIDER_CHOICES = ("ollama", "openai_compat", "lmstudio")

_BILLION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)b", re.IGNORECASE)


@dataclass(frozen=True)
class ProviderRuntimeTarget:
    requested_provider: str
    canonical_provider: str
    requested_model: str
    model_id: str
    base_url: str
    resolution_mode: str
    inventory_source: str
    available_models: tuple[str, ...]
    loaded_models_before: tuple[str, ...]
    loaded_models_after: tuple[str, ...]
    auto_load_attempted: bool
    auto_load_performed: bool
    status: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def normalize_provider(provider: str) -> str:
    raw = str(provider or "").strip().lower()
    return "openai_compat" if raw in {"lmstudio", "openai_compat"} else "ollama"


def effective_provider(provider: str | None, *, default: str) -> str:
    requested = str(provider or "").strip().lower() or str(default or "").strip().lower() or "ollama"
    return requested if requested in PROVIDER_CHOICES else requested


def default_base_url(provider: str) -> str:
    if normalize_provider(provider) == "openai_compat":
        for key in ("ORKET_LLM_OPENAI_BASE_URL", "ORKET_MODEL_STREAM_OPENAI_BASE_URL"):
            raw = str(os.getenv(key, "")).strip()
            if raw:
                return raw
        return "http://127.0.0.1:1234/v1"
    for key in ("ORKET_LLM_OLLAMA_HOST", "OLLAMA_HOST"):
        raw = str(os.getenv(key, "")).strip()
        if raw:
            return raw
    return "http://127.0.0.1:11434"


def normalize_base_url(raw: str | None, *, default: str) -> str:
    value = str(raw or "").strip() or str(default or "").strip()
    if "://" not in value:
        value = f"http://{value}"
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base URL '{value}'")
    base = f"{parsed.scheme}://{parsed.netloc}"
    path = parsed.path.rstrip("/")
    return f"{base}{path}" if path else base


def resolve_bool_env(*keys: str, default: bool) -> bool:
    for key in keys:
        raw = str(os.getenv(key, "")).strip().lower()
        if raw in {"1", "true", "yes", "on"}:
            return True
        if raw in {"0", "false", "no", "off"}:
            return False
    return default


def resolve_float_env(*keys: str, default: float) -> float:
    for key in keys:
        raw = str(os.getenv(key, "")).strip()
        if not raw:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return float(default)


def resolve_int_env(*keys: str, default: int) -> int:
    for key in keys:
        raw = str(os.getenv(key, "")).strip()
        if not raw:
            continue
        try:
            return int(raw)
        except ValueError:
            continue
    return int(default)


def _extract_model_size_b(model_lower: str) -> float | None:
    match = _BILLION_PATTERN.search(model_lower)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _model_score(model_id: str, preferred_model: str) -> tuple[int, str]:
    model = str(model_id or "").strip()
    model_lower = model.lower()
    preferred = str(preferred_model or "").strip().lower()
    score = 0
    if preferred and model_lower == preferred:
        score += 1000
    if preferred and preferred in model_lower:
        score += 250
    if "coder" in model_lower:
        score += 80
    if model_lower.startswith("qwen"):
        score += 60
    elif "qwen" in model_lower:
        score += 40
    if "deepseek" in model_lower:
        score += 20
    if "embed" in model_lower or "embedding" in model_lower:
        score -= 300
    if model_lower.endswith(":latest"):
        score -= 10
    size_b = _extract_model_size_b(model_lower)
    if size_b is not None:
        score += 8 if size_b <= 16 else (-8 if size_b >= 70 else 0)
    return score, model


def rank_models(models: list[str], *, preferred_model: str = "") -> list[str]:
    unique = sorted({str(model).strip() for model in models if str(model).strip()})
    return sorted(unique, key=lambda model: _model_score(model, preferred_model), reverse=True)


def choose_model(models: list[str], *, preferred_model: str = "") -> str:
    ranked = rank_models(models, preferred_model=preferred_model)
    return ranked[0] if ranked else ""


def _supports_lmstudio_cli_warmup(*, provider: str, base_url: str) -> bool:
    requested = effective_provider(provider, default="ollama")
    if requested == "lmstudio":
        return True
    if normalize_provider(requested) != "openai_compat":
        return False
    parsed = urlparse(base_url)
    host = str(parsed.hostname or "").strip().lower()
    port = int(parsed.port or (443 if parsed.scheme == "https" else 80))
    return host in {"127.0.0.1", "localhost"} and port == 1234


async def list_provider_models(
    *,
    provider: str,
    base_url: str | None,
    timeout_s: float,
    api_key: str | None = None,
) -> dict[str, object]:
    requested = effective_provider(provider, default="ollama")
    canonical = normalize_provider(requested)
    resolved_base_url = normalize_base_url(base_url, default=default_base_url(requested))
    if requested == "lmstudio":
        models = await asyncio.to_thread(_list_installed_lmstudio_models_sync, timeout_s=timeout_s)
        return {
            "requested_provider": requested,
            "canonical_provider": canonical,
            "base_url": resolved_base_url,
            "models": models,
        }
    models = (
        await _list_openai_compat_models(base_url=resolved_base_url, api_key=api_key, timeout_s=timeout_s)
        if canonical == "openai_compat"
        else await _list_ollama_models(base_url=resolved_base_url, timeout_s=timeout_s)
    )
    return {
        "requested_provider": requested,
        "canonical_provider": canonical,
        "base_url": resolved_base_url,
        "models": models,
    }


def _target_payload(
    *,
    requested_provider: str,
    canonical_provider: str,
    requested_model: str,
    model_id: str,
    base_url: str,
    resolution_mode: str,
    inventory_source: str,
    available_models: list[str],
    loaded_models_before: list[str] | None = None,
    loaded_models_after: list[str] | None = None,
    auto_load_attempted: bool = False,
    auto_load_performed: bool = False,
    status: str = "OK",
) -> ProviderRuntimeTarget:
    return ProviderRuntimeTarget(
        requested_provider=requested_provider,
        canonical_provider=canonical_provider,
        requested_model=requested_model,
        model_id=model_id,
        base_url=base_url,
        resolution_mode=resolution_mode,
        inventory_source=inventory_source,
        available_models=tuple(available_models),
        loaded_models_before=tuple(loaded_models_before or []),
        loaded_models_after=tuple(loaded_models_after or []),
        auto_load_attempted=auto_load_attempted,
        auto_load_performed=auto_load_performed,
        status=status,
    )


async def resolve_provider_runtime_target(
    *,
    provider: str,
    requested_model: str,
    base_url: str | None,
    timeout_s: float,
    auto_select_model: bool,
    auto_load_local_model: bool,
    model_load_timeout_s: float,
    model_ttl_sec: int,
    api_key: str | None = None,
) -> ProviderRuntimeTarget:
    requested_provider = effective_provider(provider, default="ollama")
    try:
        requested_provider = validate_allowed_token(
            token=requested_provider,
            allowed=PROVIDER_CHOICES,
            error_code_prefix="E_UNKNOWN_PROVIDER_INPUT",
        )
    except ValueError:
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider="unknown",
            requested_model=str(requested_model or "").strip(),
            model_id="",
            base_url=normalize_base_url(base_url, default=default_base_url("ollama")),
            resolution_mode="unknown_provider_input",
            inventory_source="unknown_input_policy",
            available_models=[],
            status="BLOCKED",
        )
    canonical_provider = normalize_provider(requested_provider)
    resolved_base_url = normalize_base_url(base_url, default=default_base_url(requested_provider))
    requested_model_token = str(requested_model or "").strip()
    quarantine_policy = resolve_provider_quarantine_policy()
    quarantined_providers = {str(token).strip().lower() for token in (quarantine_policy.get("providers") or [])}
    quarantined_provider_models = {
        (str(row[0]).strip().lower(), str(row[1]).strip())
        for row in (quarantine_policy.get("provider_models") or [])
        if isinstance(row, (tuple, list)) and len(row) == 2
    }
    if is_provider_quarantined(
        requested_provider=requested_provider,
        canonical_provider=canonical_provider,
        quarantined_providers=quarantined_providers,
    ):
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id="",
            base_url=resolved_base_url,
            resolution_mode="quarantined_provider",
            inventory_source="quarantine_policy",
            available_models=[],
            status="BLOCKED",
        )
    if canonical_provider == "ollama":
        available_models = await asyncio.to_thread(_list_installed_ollama_models_sync, timeout_s=timeout_s)
        resolved_model = requested_model_token if requested_model_token in available_models else ""
        resolution_mode = "requested" if resolved_model else "unresolved"
        if not resolved_model and (auto_select_model or not requested_model_token):
            resolved_model = choose_model(available_models, preferred_model=requested_model_token)
            resolution_mode = "auto_selected" if resolved_model else "unresolved"
        if resolved_model and is_model_quarantined(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            model_id=resolved_model,
            quarantined_provider_models=quarantined_provider_models,
        ):
            return _target_payload(
                requested_provider=requested_provider,
                canonical_provider=canonical_provider,
                requested_model=requested_model_token,
                model_id=resolved_model,
                base_url=resolved_base_url,
                resolution_mode="quarantined_model",
                inventory_source="quarantine_policy",
                available_models=available_models,
                status="BLOCKED",
            )
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=resolved_model,
            base_url=resolved_base_url,
            resolution_mode=resolution_mode,
            inventory_source="ollama_list",
            available_models=available_models,
            status="OK" if resolved_model else "BLOCKED",
        )
    if not _supports_lmstudio_cli_warmup(provider=requested_provider, base_url=resolved_base_url):
        listing = await list_provider_models(
            provider=requested_provider,
            base_url=resolved_base_url,
            timeout_s=timeout_s,
            api_key=api_key,
        )
        available_models = [str(model) for model in (listing.get("models") or [])]
        resolved_model = requested_model_token if requested_model_token in available_models else ""
        resolution_mode = "requested" if resolved_model else "unresolved"
        if not resolved_model and (auto_select_model or not requested_model_token):
            resolved_model = choose_model(available_models, preferred_model=requested_model_token)
            resolution_mode = "auto_selected" if resolved_model else "unresolved"
        if resolved_model and is_model_quarantined(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            model_id=resolved_model,
            quarantined_provider_models=quarantined_provider_models,
        ):
            return _target_payload(
                requested_provider=requested_provider,
                canonical_provider=canonical_provider,
                requested_model=requested_model_token,
                model_id=resolved_model,
                base_url=resolved_base_url,
                resolution_mode="quarantined_model",
                inventory_source="quarantine_policy",
                available_models=available_models,
                status="BLOCKED",
            )
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=resolved_model,
            base_url=resolved_base_url,
            resolution_mode=resolution_mode,
            inventory_source="http_models",
            available_models=available_models,
            status="OK" if resolved_model else "BLOCKED",
        )

    available_models = await asyncio.to_thread(_list_installed_lmstudio_models_sync, timeout_s=timeout_s)
    loaded_models_before = await asyncio.to_thread(_list_loaded_lmstudio_model_ids_sync, timeout_s=timeout_s)
    if (
        requested_model_token
        and requested_model_token in loaded_models_before
        and is_model_quarantined(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            model_id=requested_model_token,
            quarantined_provider_models=quarantined_provider_models,
        )
    ):
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=requested_model_token,
            base_url=resolved_base_url,
            resolution_mode="quarantined_model",
            inventory_source="quarantine_policy",
            available_models=available_models,
            loaded_models_before=loaded_models_before,
            loaded_models_after=loaded_models_before,
            status="BLOCKED",
        )
    if requested_model_token and requested_model_token in loaded_models_before:
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=requested_model_token,
            base_url=resolved_base_url,
            resolution_mode="requested_loaded",
            inventory_source="lms_cli",
            available_models=available_models,
            loaded_models_before=loaded_models_before,
            loaded_models_after=loaded_models_before,
        )
    candidate = ""
    resolution_mode = "unresolved"
    if requested_model_token and requested_model_token in available_models:
        candidate = requested_model_token
        resolution_mode = "requested_from_disk"
    elif auto_select_model or not requested_model_token:
        candidate = choose_model(loaded_models_before, preferred_model=requested_model_token)
        resolution_mode = "auto_selected_loaded" if candidate else "unresolved"
        if not candidate:
            candidate = choose_model(available_models, preferred_model=requested_model_token)
            if candidate:
                resolution_mode = "auto_selected_from_disk"
    if not candidate:
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id="",
            base_url=resolved_base_url,
            resolution_mode=resolution_mode,
            inventory_source="lms_cli",
            available_models=available_models,
            loaded_models_before=loaded_models_before,
            loaded_models_after=loaded_models_before,
            status="BLOCKED",
        )
    if is_model_quarantined(
        requested_provider=requested_provider,
        canonical_provider=canonical_provider,
        model_id=candidate,
        quarantined_provider_models=quarantined_provider_models,
    ):
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=candidate,
            base_url=resolved_base_url,
            resolution_mode="quarantined_model",
            inventory_source="quarantine_policy",
            available_models=available_models,
            loaded_models_before=loaded_models_before,
            loaded_models_after=loaded_models_before,
            status="BLOCKED",
        )
    if candidate in loaded_models_before or not auto_load_local_model:
        return _target_payload(
            requested_provider=requested_provider,
            canonical_provider=canonical_provider,
            requested_model=requested_model_token,
            model_id=candidate,
            base_url=resolved_base_url,
            resolution_mode=resolution_mode,
            inventory_source="lms_cli",
            available_models=available_models,
            loaded_models_before=loaded_models_before,
            loaded_models_after=loaded_models_before,
            auto_load_attempted=candidate not in loaded_models_before,
            status="OK" if candidate in loaded_models_before else "BLOCKED",
        )
    await asyncio.to_thread(
        _load_lmstudio_model_sync,
        model_key=candidate,
        timeout_s=model_load_timeout_s,
        ttl_sec=model_ttl_sec,
    )
    loaded_models_after = await asyncio.to_thread(_list_loaded_lmstudio_model_ids_sync, timeout_s=timeout_s)
    return _target_payload(
        requested_provider=requested_provider,
        canonical_provider=canonical_provider,
        requested_model=requested_model_token,
        model_id=candidate,
        base_url=resolved_base_url,
        resolution_mode=resolution_mode,
        inventory_source="lms_cli",
        available_models=available_models,
        loaded_models_before=loaded_models_before,
        loaded_models_after=loaded_models_after,
        auto_load_attempted=True,
        auto_load_performed=True,
    )


def list_provider_models_sync(
    *,
    provider: str,
    base_url: str | None,
    timeout_s: float,
    api_key: str | None = None,
) -> dict[str, object]:
    return _run_coro_sync(
        list_provider_models(
            provider=provider,
            base_url=base_url,
            timeout_s=timeout_s,
            api_key=api_key,
        )
    )


def resolve_provider_runtime_target_sync(**kwargs: Any) -> dict[str, Any]:
    result = _run_coro_sync(resolve_provider_runtime_target(**kwargs))
    return result.to_payload()
