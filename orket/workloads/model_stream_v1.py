from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import Mapping
from typing import Any

from orket.application.interactions.context import InteractionContext
from orket.application.services.process_input_service import capture_process_context
from orket.core.contracts.interaction_stream import CommitIntent, StreamEventType
from orket.core.contracts.provider_preparation import ProviderPreparationRequest, require_prepared_target
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL, PROVIDER_CHOICES, provider_from_environment
from orket.runtime.config.provider_runtime_target import (
    default_base_url,
    resolve_bool_env,
    resolve_float_env,
    resolve_int_env,
    resolve_provider_runtime_target,
)
from orket.streaming.model_provider import (
    ModelStreamProvider,
    OllamaModelStreamProvider,
    OpenAICompatModelStreamProvider,
    ProviderEvent,
    ProviderEventType,
    ProviderTurnRequest,
    StubModelStreamProvider,
)


def _provider_mode(environment: Mapping[str, str]) -> str:
    return str(environment.get("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()


def _real_model_id(input_config: dict[str, Any], turn_params: dict[str, Any], environment: Mapping[str, str]) -> str:
    return str(
        input_config.get("model_id")
        or turn_params.get("model_id")
        or environment.get("ORKET_MODEL_STREAM_REAL_MODEL_ID", DEFAULT_LOCAL_MODEL)
    ).strip()


def _real_provider_name(environment: Mapping[str, str]) -> str:
    return provider_from_environment(environment, "ORKET_MODEL_STREAM_REAL_PROVIDER", "ORKET_LLM_PROVIDER", "ORKET_MODEL_PROVIDER")


def _openai_base_url(environment: Mapping[str, str]) -> str:
    return str(environment.get("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")).strip()


def _real_timeout_s(environment: Mapping[str, str]) -> float:
    return resolve_float_env("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", default=20.0, environment=environment)


async def _build_real_provider(*, input_config: dict[str, Any], turn_params: dict[str, Any],
                               environment: Mapping[str, str]) -> ModelStreamProvider:
    cwd, environment = capture_process_context(environment=environment)
    requested_provider = _real_provider_name(environment)
    timeout_s = _real_timeout_s(environment)
    requested_model = _real_model_id(input_config, turn_params, environment)
    requested_base_url = _openai_base_url(environment) if requested_provider in {"openai_compat", "lmstudio"} else None
    target = await resolve_provider_runtime_target(
        provider=requested_provider,
        requested_model=requested_model,
        base_url=requested_base_url,
        timeout_s=timeout_s,
        auto_select_model=resolve_bool_env(
            "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL",
            "ORKET_MODEL_STREAM_AUTO_SELECT_MODEL",
            default=True, environment=environment,
        ),
        auto_load_local_model=resolve_bool_env(
            "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL",
            "ORKET_MODEL_STREAM_AUTO_LOAD_LOCAL_MODEL",
            default=True, environment=environment,
        ),
        model_load_timeout_s=resolve_float_env(
            "ORKET_PROVIDER_RUNTIME_MODEL_LOAD_TIMEOUT_SEC",
            "ORKET_MODEL_STREAM_MODEL_LOAD_TIMEOUT_SEC",
            default=180.0, environment=environment,
        ),
        model_ttl_sec=resolve_int_env(
            "ORKET_PROVIDER_RUNTIME_MODEL_TTL_SEC",
            "ORKET_MODEL_STREAM_MODEL_TTL_SEC",
            default=600, environment=environment,
        ),
        api_key=str(environment.get("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None,
        environment=environment, cwd=cwd,
    )
    if not str(target.model_id or "").strip():
        available = ", ".join(target.available_models[:12]) or "(no models discovered)"
        raise ValueError(
            "Provider runtime target resolution failed "
            f"provider={target.requested_provider} requested_model={target.requested_model or '(unset)'} "
            f"resolution_mode={target.resolution_mode} available={available}"
        )
    request = ProviderPreparationRequest(
        provider=requested_provider, requested_model=requested_model,
        base_url=requested_base_url or default_base_url(requested_provider, environment=environment),
        timeout_s=timeout_s, api_key=str(environment.get("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip(),
    )
    require_prepared_target(request, target)
    if target.canonical_provider == "ollama":
        return OllamaModelStreamProvider(model_id=target.model_id, base_url=target.base_url, timeout_s=timeout_s)
    return OpenAICompatModelStreamProvider(
        model_id=target.model_id,
        base_url=target.base_url,
        provider_name=target.requested_provider,
        api_key=str(environment.get("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None,
        timeout_s=timeout_s,
    )


def _build_provider(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> ModelStreamProvider:
    environment = dict(os.environ)
    mode = _provider_mode(environment)
    if mode == "stub":
        return StubModelStreamProvider()
    if mode == "real":
        raise ValueError("Real provider construction is async-only. Use run_model_stream_v1.")
    raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")


def validate_model_stream_v1_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    # Build-time validation is used by the API for fail-fast diagnostics before turn execution.
    environment = dict(os.environ)
    mode = _provider_mode(environment)
    if mode == "stub":
        return
    if mode != "real":
        raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")
    provider_name = _real_provider_name(environment)
    if provider_name not in PROVIDER_CHOICES:
        raise ValueError(
            f"Unsupported ORKET_MODEL_STREAM_REAL_PROVIDER='{provider_name}'. Expected: llama_cpp|lmstudio|ollama|openai_compat."
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


def _turn_timeout_s(environment: Mapping[str, str]) -> float:
    turn_timeout_raw = str(environment.get("ORKET_MODEL_STREAM_TURN_TIMEOUT_S", "12")).strip()
    try:
        turn_timeout_s = max(1.0, float(turn_timeout_raw))
    except ValueError:
        turn_timeout_s = 12.0

    return turn_timeout_s


async def run_model_stream_v1(
    *,
    input_config: dict[str, Any],
    turn_params: dict[str, Any],
    interaction_context: InteractionContext,
) -> dict[str, int]:
    environment = dict(os.environ)
    req = ProviderTurnRequest(input_config=input_config, turn_params=turn_params).model_copy(deep=True)
    turn_timeout_s = _turn_timeout_s(environment)
    provider = (
        StubModelStreamProvider()
        if _provider_mode(environment) == "stub"
        else await _build_real_provider(input_config=req.input_config, turn_params=req.turn_params, environment=environment)
    )
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

    cancel_task = asyncio.create_task(_cancel_watch())
    try:
        try:
            await asyncio.wait_for(_consume_provider(), timeout=turn_timeout_s)
        except TimeoutError:
            provider_error = f"provider_turn_timeout:{turn_timeout_s}s"
    finally:
        cancel_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await cancel_task

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
