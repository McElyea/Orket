from __future__ import annotations

import os
import re
from urllib.parse import urlparse

import httpx


PROVIDER_CHOICES = ("ollama", "openai_compat", "lmstudio")


_BILLION_PATTERN = re.compile(r"(\d+(?:\.\d+)?)b", re.IGNORECASE)


def _extract_model_size_b(model_lower: str) -> float | None:
    match = _BILLION_PATTERN.search(model_lower)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def normalize_provider(provider: str) -> str:
    raw = str(provider or "").strip().lower()
    if raw == "lmstudio":
        return "openai_compat"
    if raw == "openai_compat":
        return "openai_compat"
    return "ollama"


def effective_provider(provider: str | None, *, default: str) -> str:
    requested = str(provider or "").strip().lower() or str(default or "").strip().lower() or "ollama"
    if requested not in PROVIDER_CHOICES:
        return requested
    return requested


def default_base_url(provider: str) -> str:
    canonical = normalize_provider(provider)
    if canonical == "openai_compat":
        raw = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "")).strip()
        return raw or "http://127.0.0.1:1234/v1"
    raw = str(os.getenv("OLLAMA_HOST", "")).strip()
    return raw or "http://127.0.0.1:11434"


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


def _list_openai_compat_models(*, base_url: str, api_key: str | None, timeout_s: float) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s), headers=headers) as client:
        resp = client.get("/models")
        resp.raise_for_status()
        payload = resp.json() if isinstance(resp.json(), dict) else {}
    data = payload.get("data")
    model_ids: list[str] = []
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if model_id:
                model_ids.append(model_id)
    return sorted(set(model_ids))


def _list_ollama_models(*, base_url: str, timeout_s: float) -> list[str]:
    with httpx.Client(base_url=base_url, timeout=max(1.0, timeout_s)) as client:
        resp = client.get("/api/tags")
        resp.raise_for_status()
        payload = resp.json() if isinstance(resp.json(), dict) else {}
    models = payload.get("models")
    model_ids: list[str] = []
    if isinstance(models, list):
        for row in models:
            if not isinstance(row, dict):
                continue
            for key in ("name", "model"):
                value = str(row.get(key) or "").strip()
                if value:
                    model_ids.append(value)
    return sorted(set(model_ids))


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
        model_ids = _list_openai_compat_models(base_url=resolved_base_url, api_key=api_key, timeout_s=timeout_s)
    else:
        model_ids = _list_ollama_models(base_url=resolved_base_url, timeout_s=timeout_s)
    return {
        "requested_provider": requested,
        "canonical_provider": canonical,
        "base_url": resolved_base_url,
        "models": model_ids,
    }


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
        if size_b <= 16:
            score += 8
        elif size_b >= 70:
            score -= 8
    return score, model


def rank_models(models: list[str], *, preferred_model: str = "") -> list[str]:
    unique = sorted({str(model).strip() for model in models if str(model).strip()})
    ranked = sorted(unique, key=lambda model: _model_score(model, preferred_model), reverse=True)
    return ranked


def choose_model(models: list[str], *, preferred_model: str = "") -> str:
    ranked = rank_models(models, preferred_model=preferred_model)
    return ranked[0] if ranked else ""
