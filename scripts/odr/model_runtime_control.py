from __future__ import annotations

import asyncio
import subprocess
import time
from typing import Any

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.runtime.provider_runtime_inventory import list_loaded_lmstudio_model_ids_sync
from scripts.providers.lmstudio_model_cache import clear_loaded_models, default_lmstudio_base_url

DEFAULT_SWAP_TIMEOUT_SEC = 30.0
DEFAULT_SWAP_POLL_INTERVAL_SEC = 0.25


def _run_command(cmd: list[str], *, timeout_s: float) -> str:
    result = subprocess.run(
        cmd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=max(1.0, float(timeout_s)),
    )
    if int(result.returncode) != 0:
        detail = str(result.stderr or "").strip() or str(result.stdout or "").strip() or f"exit={result.returncode}"
        raise RuntimeError(f"command failed: {' '.join(cmd)} ({detail})")
    return str(result.stdout or "")


def _parse_ollama_ps(stdout: str) -> list[str]:
    models: list[str] = []
    for raw_line in str(stdout or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("NAME"):
            continue
        token = line.split()[0].strip()
        if token:
            models.append(token)
    return models


def _list_loaded_ollama_models_sync(*, timeout_s: float) -> list[str]:
    return _parse_ollama_ps(_run_command(["ollama", "ps"], timeout_s=timeout_s))


def _stop_ollama_model_sync(*, model_id: str, timeout_s: float) -> None:
    token = str(model_id or "").strip()
    if not token:
        return
    _run_command(["ollama", "stop", token], timeout_s=timeout_s)


def release_model_residency_sync(
    *,
    provider_name: str,
    model_id: str,
    base_url: str = "",
    timeout_s: float = DEFAULT_SWAP_TIMEOUT_SEC,
    poll_interval_s: float = DEFAULT_SWAP_POLL_INTERVAL_SEC,
) -> dict[str, Any]:
    provider_token = str(provider_name or "").strip().lower()
    model_token = str(model_id or "").strip()
    if not model_token:
        return {"status": "skipped", "reason": "empty_model", "provider": provider_token}

    if provider_token == "ollama":
        loaded_before = _list_loaded_ollama_models_sync(timeout_s=timeout_s)
        unload_attempted = model_token in loaded_before
        if unload_attempted:
            _stop_ollama_model_sync(model_id=model_token, timeout_s=timeout_s)
        deadline = time.monotonic() + max(1.0, float(timeout_s))
        polls = 0
        while True:
            loaded_after = _list_loaded_ollama_models_sync(timeout_s=timeout_s)
            if model_token not in loaded_after:
                return {
                    "status": "released",
                    "provider": provider_token,
                    "model_id": model_token,
                    "loaded_before": loaded_before,
                    "loaded_after": loaded_after,
                    "unload_attempted": unload_attempted,
                    "polls": polls,
                }
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"Ollama model swap timeout waiting for {model_token} to unload; loaded_after={loaded_after}"
                )
            polls += 1
            time.sleep(max(0.01, float(poll_interval_s)))

    if provider_token == "lmstudio":
        resolved_base_url = str(base_url or default_lmstudio_base_url()).strip() or default_lmstudio_base_url()
        loaded_before = list_loaded_lmstudio_model_ids_sync(timeout_s=timeout_s)
        clear_result = clear_loaded_models(
            stage="odr_model_swap",
            base_url=resolved_base_url,
            timeout_sec=max(1, int(timeout_s)),
            strict=True,
        )
        deadline = time.monotonic() + max(1.0, float(timeout_s))
        polls = 0
        while True:
            loaded_after = list_loaded_lmstudio_model_ids_sync(timeout_s=timeout_s)
            if not loaded_after:
                return {
                    "status": "released",
                    "provider": provider_token,
                    "model_id": model_token,
                    "base_url": resolved_base_url,
                    "loaded_before": loaded_before,
                    "loaded_after": loaded_after,
                    "unload_result": clear_result,
                    "polls": polls,
                }
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"LM Studio model swap timeout waiting for cache to clear; loaded_after={loaded_after}"
                )
            polls += 1
            time.sleep(max(0.01, float(poll_interval_s)))

    return {
        "status": "unsupported",
        "reason": "provider_not_supported",
        "provider": provider_token,
        "model_id": model_token,
    }


async def release_model_residency(
    *,
    provider_name: str,
    model_id: str,
    base_url: str = "",
    timeout_s: float = DEFAULT_SWAP_TIMEOUT_SEC,
    poll_interval_s: float = DEFAULT_SWAP_POLL_INTERVAL_SEC,
) -> dict[str, Any]:
    return await asyncio.to_thread(
        release_model_residency_sync,
        provider_name=provider_name,
        model_id=model_id,
        base_url=base_url,
        timeout_s=timeout_s,
        poll_interval_s=poll_interval_s,
    )


async def complete_with_transient_provider(
    *,
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    timeout: int,
    provider_name: str = "",
    base_url: str = "",
    api_key: str = "",
    swap_timeout_s: float = DEFAULT_SWAP_TIMEOUT_SEC,
    swap_poll_interval_s: float = DEFAULT_SWAP_POLL_INTERVAL_SEC,
) -> tuple[ModelResponse, int, dict[str, Any]]:
    provider = LocalModelProvider(
        model=model,
        temperature=temperature,
        timeout=timeout,
        provider=provider_name,
        base_url=base_url,
        api_key=api_key,
    )
    started_at = time.perf_counter()
    response: ModelResponse | None = None
    release_payload: dict[str, Any] = {}
    call_error: Exception | None = None

    try:
        response = await provider.complete(messages)
    except Exception as exc:  # noqa: BLE001
        call_error = exc
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    close_error: Exception | None = None
    try:
        await provider.close()
    except Exception as exc:  # noqa: BLE001
        close_error = exc

    provider_name = str(getattr(provider, "provider_name", "") or getattr(provider, "provider_backend", "") or "")
    base_url = (
        str(getattr(provider, "openai_base_url", "") or "")
        if provider_name in {"lmstudio", "openai_compat"}
        else str(getattr(provider, "ollama_host", "") or "")
    )
    resolved_model = str(getattr(provider, "model", "") or model)

    try:
        release_payload = await release_model_residency(
            provider_name=provider_name,
            model_id=resolved_model,
            base_url=base_url,
            timeout_s=swap_timeout_s,
            poll_interval_s=swap_poll_interval_s,
        )
    except Exception as release_exc:  # noqa: BLE001
        if call_error is None and close_error is None:
            raise
        release_payload = {
            "status": "release_error_after_call_failure",
            "provider": provider_name,
            "model_id": resolved_model,
            "error": str(release_exc),
        }

    if call_error is not None:
        raise call_error
    if close_error is not None:
        raise close_error
    if response is None:
        raise RuntimeError(f"Transient provider call returned no response for model={model}")
    return response, latency_ms, release_payload
