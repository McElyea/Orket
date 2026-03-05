from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen


class LmStudioCacheClearError(RuntimeError):
    """Raised when LM Studio model-cache sanitation fails."""

    def __init__(self, message: str, *, result: dict[str, Any] | None = None):
        super().__init__(message)
        self.result = result or {}


def default_lmstudio_base_url() -> str:
    for key in ("ORKET_LMSTUDIO_BASE_URL", "ORKET_LLM_OPENAI_BASE_URL"):
        value = str(os.environ.get(key, "")).strip()
        if value:
            return value
    return "http://127.0.0.1:1234"


def _resolve_lmstudio_endpoints(base_url: str) -> tuple[str, str, str]:
    token = str(base_url or "").strip()
    parsed = urlparse(token)
    if not parsed.scheme or not parsed.netloc:
        raise LmStudioCacheClearError(
            "--lmstudio-base-url must be an absolute URL such as http://127.0.0.1:1234 or http://127.0.0.1:1234/v1"
        )
    root_path = str(parsed.path or "").rstrip("/")
    if root_path.endswith("/api/v1"):
        root_path = root_path[: -len("/api/v1")]
    elif root_path.endswith("/v1"):
        root_path = root_path[: -len("/v1")]
    root_path = root_path.rstrip("/")
    models_path = f"{root_path}/v1/models" if root_path else "/v1/models"
    api_models_path = f"{root_path}/api/v1/models" if root_path else "/api/v1/models"
    unload_path = f"{root_path}/api/v1/models/unload" if root_path else "/api/v1/models/unload"
    models_url = urlunparse((parsed.scheme, parsed.netloc, models_path, "", "", ""))
    api_models_url = urlunparse((parsed.scheme, parsed.netloc, api_models_path, "", "", ""))
    unload_url = urlunparse((parsed.scheme, parsed.netloc, unload_path, "", "", ""))
    return models_url, api_models_url, unload_url


def _request_json(*, method: str, url: str, timeout_sec: int, payload: dict[str, Any] | None = None) -> Any:
    body = None
    headers: dict[str, str] = {}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url=url, data=body, method=method, headers=headers)
    timeout = max(1, int(timeout_sec))
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace").strip()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise LmStudioCacheClearError(f"{method} {url} -> HTTP {int(exc.code)}: {detail}") from exc
    except URLError as exc:
        raise LmStudioCacheClearError(f"{method} {url} failed: {exc.reason}") from exc

    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LmStudioCacheClearError(f"{method} {url} returned non-JSON payload") from exc


def _list_loaded_instance_ids(*, api_models_url: str, timeout_sec: int) -> list[str]:
    payload = _request_json(method="GET", url=api_models_url, timeout_sec=timeout_sec)
    if not isinstance(payload, dict):
        raise LmStudioCacheClearError(f"GET {api_models_url} returned invalid payload shape")
    models = payload.get("models")
    if not isinstance(models, list):
        raise LmStudioCacheClearError(f"GET {api_models_url} missing 'models' array")
    resolved: list[str] = []
    for row in models:
        if not isinstance(row, dict):
            continue
        loaded_instances = row.get("loaded_instances")
        if not isinstance(loaded_instances, list):
            continue
        for loaded in loaded_instances:
            if not isinstance(loaded, dict):
                continue
            instance_id = str(loaded.get("id") or "").strip()
            if instance_id:
                resolved.append(instance_id)
    return resolved


def clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool = True) -> dict[str, Any]:
    models_url, api_models_url, unload_url = _resolve_lmstudio_endpoints(base_url)
    loaded_before = _list_loaded_instance_ids(api_models_url=api_models_url, timeout_sec=timeout_sec)
    unloaded: list[str] = []
    errors: list[str] = []
    for instance_id in loaded_before:
        try:
            _request_json(
                method="POST",
                url=unload_url,
                timeout_sec=timeout_sec,
                payload={"instance_id": instance_id},
            )
        except LmStudioCacheClearError as exc:
            errors.append(str(exc))
        else:
            unloaded.append(instance_id)
    remaining = _list_loaded_instance_ids(api_models_url=api_models_url, timeout_sec=timeout_sec)
    status = "OK" if not errors and not remaining else "FAILED"
    result = {
        "stage": str(stage),
        "status": status,
        "base_url": str(base_url),
        "models_url": models_url,
        "api_models_url": api_models_url,
        "unload_url": unload_url,
        "loaded_before": loaded_before,
        "unloaded": unloaded,
        "remaining": remaining,
        "errors": errors,
    }
    if strict and status != "OK":
        raise LmStudioCacheClearError(f"LM Studio model-cache sanitation failed: {json.dumps(result, indent=2)}", result=result)
    return result

