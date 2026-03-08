from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any

import httpx


class ProviderRuntimeWarmupError(RuntimeError):
    """Raised when provider runtime preparation cannot resolve a runnable target."""


def _run_coro_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("Synchronous provider runtime helpers cannot be used while an event loop is running.")


def _run_command_sync(cmd: list[str], *, timeout_s: float) -> str:
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(1.0, float(timeout_s)),
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired) as exc:
        raise ProviderRuntimeWarmupError(f"command failed: {' '.join(cmd)} ({exc})") from exc
    if int(result.returncode) != 0:
        detail = str(result.stderr or "").strip() or str(result.stdout or "").strip() or f"exit={result.returncode}"
        raise ProviderRuntimeWarmupError(f"command failed: {' '.join(cmd)} ({detail})")
    return str(result.stdout or "")


def _parse_ollama_list(stdout: str) -> list[str]:
    models: list[str] = []
    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("NAME"):
            continue
        token = line.split()[0].strip()
        if token:
            models.append(token)
    return sorted(set(models))


def list_installed_ollama_models_sync(*, timeout_s: float) -> list[str]:
    return _parse_ollama_list(_run_command_sync(["ollama", "list"], timeout_s=timeout_s))


def _load_json_command_sync(cmd: list[str], *, timeout_s: float) -> Any:
    stdout = _run_command_sync(cmd, timeout_s=timeout_s)
    try:
        return json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeWarmupError(f"command returned invalid JSON: {' '.join(cmd)}") from exc


def list_installed_lmstudio_models_sync(*, timeout_s: float) -> list[str]:
    payload = _load_json_command_sync(["lms", "ls", "--json"], timeout_s=timeout_s)
    if not isinstance(payload, list):
        raise ProviderRuntimeWarmupError("lms ls --json returned invalid payload shape")
    models = [str(row.get("modelKey") or "").strip() for row in payload if isinstance(row, dict)]
    return sorted({model for model in models if model})


def list_loaded_lmstudio_model_ids_sync(*, timeout_s: float) -> list[str]:
    payload = _load_json_command_sync(["lms", "ps", "--json"], timeout_s=timeout_s)
    if not isinstance(payload, list):
        raise ProviderRuntimeWarmupError("lms ps --json returned invalid payload shape")
    models: list[str] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        for key in ("identifier", "modelKey", "indexedModelIdentifier"):
            token = str(row.get(key) or "").strip()
            if token:
                models.append(token)
    return sorted(set(models))


def load_lmstudio_model_sync(*, model_key: str, timeout_s: float, ttl_sec: int) -> dict[str, Any]:
    token = str(model_key or "").strip()
    if not token:
        raise ProviderRuntimeWarmupError("lmstudio model_key is required")
    cmd = ["lms", "load", token, "-y", "--ttl", str(max(1, int(ttl_sec)))]
    stdout = _run_command_sync(cmd, timeout_s=timeout_s)
    return {"command": " ".join(cmd), "loaded_model": token, "stdout": stdout.strip()}


async def list_openai_compat_models(*, base_url: str, api_key: str | None, timeout_s: float) -> list[str]:
    headers: dict[str, str] = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    timeout = httpx.Timeout(timeout=max(1.0, float(timeout_s)))
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, headers=headers) as client:
        response = await client.get("/models")
        response.raise_for_status()
        payload = response.json() if isinstance(response.json(), dict) else {}
    model_ids: list[str] = []
    data = payload.get("data")
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            model_id = str(row.get("id") or "").strip()
            if model_id:
                model_ids.append(model_id)
    return sorted(set(model_ids))


async def list_ollama_models(*, base_url: str, timeout_s: float) -> list[str]:
    timeout = httpx.Timeout(timeout=max(1.0, float(timeout_s)))
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.get("/api/tags")
        response.raise_for_status()
        payload = response.json() if isinstance(response.json(), dict) else {}
    model_ids: list[str] = []
    models = payload.get("models")
    if isinstance(models, list):
        for row in models:
            if not isinstance(row, dict):
                continue
            for key in ("name", "model"):
                model_id = str(row.get(key) or "").strip()
                if model_id:
                    model_ids.append(model_id)
    return sorted(set(model_ids))


def list_openai_compat_models_sync(*, base_url: str, api_key: str | None, timeout_s: float) -> list[str]:
    return list(
        _run_coro_sync(
            list_openai_compat_models(
                base_url=base_url,
                api_key=api_key,
                timeout_s=timeout_s,
            )
        )
    )


def list_ollama_models_sync(*, base_url: str, timeout_s: float) -> list[str]:
    return list(_run_coro_sync(list_ollama_models(base_url=base_url, timeout_s=timeout_s)))
