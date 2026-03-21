from __future__ import annotations

import asyncio
import os
from typing import Any

from orket.runtime.defaults import DEFAULT_LOCAL_MODEL
from orket.streaming.contracts import CommitIntent, StreamEventType
from orket.streaming.manager import InteractionContext
from orket.streaming.model_provider import (
    ModelStreamProvider,
    OpenAICompatModelStreamProvider,
    OllamaModelStreamProvider,
    ProviderEvent,
    ProviderEventType,
    ProviderTurnRequest,
    StubModelStreamProvider,
)
from orket.runtime.provider_runtime_target import (
    resolve_bool_env,
    resolve_float_env,
    resolve_int_env,
    resolve_provider_runtime_target,
)


def _provider_mode() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()


def _real_model_id(input_config: dict[str, Any], turn_params: dict[str, Any]) -> str:
    return str(
        input_config.get("model_id")
        or turn_params.get("model_id")
        or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", DEFAULT_LOCAL_MODEL)
    ).strip()


def _real_provider_name() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama") or "ollama").strip().lower()


def _openai_base_url() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")).strip()


def _real_timeout_s() -> float:
    return resolve_float_env("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", default=20.0)


async def _build_real_provider(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> ModelStreamProvider:
    requested_provider = _real_provider_name()
    target = await resolve_provider_runtime_target(
        provider=requested_provider,
        requested_model=_real_model_id(input_config, turn_params),
        base_url=_openai_base_url() if requested_provider in {"openai_compat", "lmstudio"} else None,
        timeout_s=_real_timeout_s(),
        auto_select_model=resolve_bool_env(
            "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL",
            "ORKET_MODEL_STREAM_AUTO_SELECT_MODEL",
            default=True,
        ),
        auto_load_local_model=resolve_bool_env(
            "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL",
            "ORKET_MODEL_STREAM_AUTO_LOAD_LOCAL_MODEL",
            default=True,
        ),
        model_load_timeout_s=resolve_float_env(
            "ORKET_PROVIDER_RUNTIME_MODEL_LOAD_TIMEOUT_SEC",
            "ORKET_MODEL_STREAM_MODEL_LOAD_TIMEOUT_SEC",
            default=180.0,
        ),
        model_ttl_sec=resolve_int_env(
            "ORKET_PROVIDER_RUNTIME_MODEL_TTL_SEC",
            "ORKET_MODEL_STREAM_MODEL_TTL_SEC",
            default=600,
        ),
        api_key=str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None,
    )
    if not str(target.model_id or "").strip():
        available = ", ".join(target.available_models[:12]) or "(no models discovered)"
        raise ValueError(
            "Provider runtime target resolution failed "
            f"provider={target.requested_provider} requested_model={target.requested_model or '(unset)'} "
            f"resolution_mode={target.resolution_mode} available={available}"
        )
    timeout_s = _real_timeout_s()
    if target.canonical_provider == "ollama":
        return OllamaModelStreamProvider(model_id=target.model_id, base_url=target.base_url, timeout_s=timeout_s)
    return OpenAICompatModelStreamProvider(
        model_id=target.model_id,
        base_url=target.base_url,
        api_key=str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None,
        timeout_s=timeout_s,
    )


def _build_provider(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> ModelStreamProvider:
    mode = _provider_mode()
    if mode == "stub":
        return StubModelStreamProvider()
    if mode == "real":
        raise ValueError("Real provider construction is async-only. Use run_model_stream_v1.")
    raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")


def validate_model_stream_v1_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    # Build-time validation is used by the API for fail-fast diagnostics before turn execution.
    mode = _provider_mode()
    if mode == "stub":
        return
    if mode != "real":
        raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")
    provider_name = _real_provider_name()
    if provider_name not in {"ollama", "openai_compat", "lmstudio"}:
        raise ValueError(
            f"Unsupported ORKET_MODEL_STREAM_REAL_PROVIDER='{provider_name}'. Expected: ollama|openai_compat|lmstudio."
        )


def _event_mapping(event: ProviderEvent) -> tuple[StreamEventType | None, dict[str, Any]]:
    payload = dict(event.payload)
    payload["authoritative"] = False
    if event.event_type == ProviderEventType.SELECTED:
        return (StreamEventType.MODEL_SELECTED, payload)
    if event.event_type == ProviderEventType.LOADING:
        return (StreamEventType.MODEL_LOADING, payload)
    if event.event_type == ProviderEventType.READY:
        return (StreamEventType.MODEL_READY, payload)
    if event.event_type == ProviderEventType.TOKEN_DELTA:
        return (StreamEventType.TOKEN_DELTA, payload)
    return (None, payload)


async def run_model_stream_v1(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    provider = (
        StubModelStreamProvider()
        if _provider_mode() == "stub"
        else await _build_real_provider(input_config=input_config, turn_params=turn_params)
    )
    req = ProviderTurnRequest(input_config=input_config, turn_params=turn_params)
    provider_turn_id: str | None = None
    stop_reason = ""
    provider_error = ""

    async def _cancel_watch() -> None:
        await interaction_context.await_cancel()
        if provider_turn_id:
            await provider.cancel(provider_turn_id)

    async def _consume_provider() -> None:
        nonlocal provider_turn_id, provider_error, stop_reason
        async for provider_event in provider.start_turn(req):
            provider_turn_id = provider_event.provider_turn_id
            if provider_event.event_type == ProviderEventType.ERROR:
                provider_error = str(provider_event.payload.get("error") or "provider_error")
                break
            if provider_event.event_type == ProviderEventType.STOPPED:
                stop_reason = str(provider_event.payload.get("stop_reason") or "").strip().lower()
                break
            stream_mapping, payload = _event_mapping(provider_event)
            if stream_mapping is None:
                continue
            if interaction_context.is_canceled():
                await provider.cancel(provider_turn_id)
                break
            await interaction_context.emit_event(stream_mapping, payload)

    turn_timeout_raw = str(os.getenv("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "12")).strip()
    try:
        turn_timeout_s = max(1.0, float(turn_timeout_raw))
    except ValueError:
        turn_timeout_s = 12.0

    cancel_task = asyncio.create_task(_cancel_watch())
    try:
        try:
            await asyncio.wait_for(_consume_provider(), timeout=turn_timeout_s)
        except asyncio.TimeoutError:
            provider_error = f"provider_turn_timeout:{turn_timeout_s}s"
    finally:
        cancel_task.cancel()
        try:
            await cancel_task
        except asyncio.CancelledError:
            pass

    if provider_error:
        await interaction_context.request_commit(
            CommitIntent(type="decision", ref=f"fail_closed:provider_error:{provider_error}")
        )
        return {"post_finalize_wait_ms": 0, "request_cancel_turn": 1}

    if stop_reason == "canceled" or interaction_context.is_canceled():
        return {"post_finalize_wait_ms": 0, "request_cancel_turn": 1}

    if interaction_context.is_canceled():
        return {"post_finalize_wait_ms": 0}
    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref="model_stream_v1"))
    return {"post_finalize_wait_ms": 0}
