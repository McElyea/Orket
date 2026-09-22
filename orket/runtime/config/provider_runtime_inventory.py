from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from orket.adapters.execution.owned_io import require_sync_context
from orket.application.services.command_process_supervisor import CommandProcessSupervisor
from orket.application.services.process_input_service import capture_process_context
from orket.application.services.provider_http_service import open_provider_catalog_client
from orket.capabilities.sync_bridge import run_coro_sync as _run_coro_sync
from orket.core.contracts.owned_command import CommandExecutionUncertain


class ProviderRuntimeWarmupError(RuntimeError):
    """Raised when provider runtime preparation cannot resolve a runnable target."""


def _run_command_sync(cmd: list[str], *, timeout_s: float, cwd: Path | None = None,
                      environment: Mapping[str, str] | None = None) -> str:
    require_sync_context(code="E_PROVIDER_INVENTORY_REQUIRES_ASYNC_OWNER")
    command = tuple(cmd)
    root, environment = capture_process_context(cwd=cwd, environment=environment)
    try:
        result = _run_coro_sync(CommandProcessSupervisor(root, cancellation_event="provider_inventory_command_interrupted").run(
            command, cwd=root, environment=environment, timeout_seconds=max(1.0, float(timeout_s))))
    except OSError as exc:
        raise ProviderRuntimeWarmupError(f"command failed: {' '.join(command)} ({exc})") from exc
    if (not result.cleanup_confirmed or result.reason == "cancelled"
            or (not result.capture_complete and result.reason != "launch_failed")):
        raise CommandExecutionUncertain(result)
    if result.reason != "completed":
        detail = "; ".join((result.reason, *result.diagnostics))
        raise ProviderRuntimeWarmupError(f"command failed: {' '.join(command)} ({detail})")
    # Retain subprocess text-mode universal-newline behavior for inventory parsers.
    stdout, stderr = [value.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
                      for value in (result.stdout, result.stderr)]
    if int(result.returncode) != 0:
        detail = stderr.strip() or stdout.strip() or f"exit={result.returncode}"
        raise ProviderRuntimeWarmupError(f"command failed: {' '.join(command)} ({detail})")
    return stdout


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


def list_installed_ollama_models_sync(*, timeout_s: float, cwd: Path | None = None,
                                    environment: Mapping[str, str] | None = None) -> list[str]:
    return _parse_ollama_list(_run_command_sync(["ollama", "list"], timeout_s=timeout_s, cwd=cwd, environment=environment))


def _load_json_command_sync(cmd: list[str], *, timeout_s: float, cwd: Path | None = None,
                            environment: Mapping[str, str] | None = None) -> Any:
    stdout = _run_command_sync(cmd, timeout_s=timeout_s, cwd=cwd, environment=environment)
    try:
        return json.loads(stdout or "[]")
    except json.JSONDecodeError as exc:
        raise ProviderRuntimeWarmupError(f"command returned invalid JSON: {' '.join(cmd)}") from exc


def list_installed_lmstudio_models_sync(*, timeout_s: float, cwd: Path | None = None,
                                      environment: Mapping[str, str] | None = None) -> list[str]:
    payload = _load_json_command_sync(["lms", "ls", "--json"], timeout_s=timeout_s, cwd=cwd, environment=environment)
    if not isinstance(payload, list):
        raise ProviderRuntimeWarmupError("lms ls --json returned invalid payload shape")
    models = [str(row.get("modelKey") or "").strip() for row in payload if isinstance(row, dict)]
    return sorted({model for model in models if model})


def list_loaded_lmstudio_model_ids_sync(*, timeout_s: float, cwd: Path | None = None,
                                      environment: Mapping[str, str] | None = None) -> list[str]:
    payload = _load_json_command_sync(["lms", "ps", "--json"], timeout_s=timeout_s, cwd=cwd, environment=environment)
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


def load_lmstudio_model_sync(*, model_key: str, timeout_s: float, ttl_sec: int, cwd: Path | None = None,
                            environment: Mapping[str, str] | None = None) -> dict[str, Any]:
    token = str(model_key or "").strip()
    if not token:
        raise ProviderRuntimeWarmupError("lmstudio model_key is required")
    cmd = ["lms", "load", token, "-y", "--ttl", str(max(1, int(ttl_sec)))]
    stdout = _run_command_sync(cmd, timeout_s=timeout_s, cwd=cwd, environment=environment)
    return {"command": " ".join(cmd), "loaded_model": token, "stdout": stdout.strip()}


async def list_openai_compat_models(*, base_url: str, api_key: str | None, timeout_s: float,
                                  cwd: Path | None = None, environment: Mapping[str, str] | None = None) -> list[str]:
    async with open_provider_catalog_client(base_url=base_url, timeout_s=timeout_s, api_key=api_key,
                                           cwd=cwd, environment=environment) as client:
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


async def list_ollama_models(*, base_url: str, timeout_s: float, cwd: Path | None = None,
                             environment: Mapping[str, str] | None = None) -> list[str]:
    async with open_provider_catalog_client(base_url=base_url, timeout_s=timeout_s,
                                           cwd=cwd, environment=environment) as client:
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


def list_openai_compat_models_sync(*, base_url: str, api_key: str | None, timeout_s: float,
                                 cwd: Path | None = None, environment: Mapping[str, str] | None = None) -> list[str]:
    cwd, environment = capture_process_context(cwd=cwd, environment=environment)
    return list(
        _run_coro_sync(
            list_openai_compat_models(
                base_url=base_url,
                api_key=api_key,
                timeout_s=timeout_s, cwd=cwd, environment=environment,
            )
        )
    )


def list_ollama_models_sync(*, base_url: str, timeout_s: float, cwd: Path | None = None,
                            environment: Mapping[str, str] | None = None) -> list[str]:
    cwd, environment = capture_process_context(cwd=cwd, environment=environment)
    return list(_run_coro_sync(list_ollama_models(
        base_url=base_url, timeout_s=timeout_s, cwd=cwd, environment=environment)))
