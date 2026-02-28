from __future__ import annotations

import asyncio
import os
from typing import Any

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


def _provider_mode() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()


def _real_model_id(input_config: dict[str, Any], turn_params: dict[str, Any]) -> str:
    return str(
        input_config.get("model_id")
        or turn_params.get("model_id")
        or os.getenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "qwen2.5-coder:7b")
    ).strip()


def _real_provider_name() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama") or "ollama").strip().lower()


def _openai_base_url() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")).strip()


def _build_provider(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> ModelStreamProvider:
    mode = _provider_mode()
    if mode == "stub":
        return StubModelStreamProvider()
    if mode == "real":
        model_id = _real_model_id(input_config, turn_params)
        if not model_id:
            raise ValueError("ORKET_MODEL_STREAM_PROVIDER=real requires a model_id.")
        timeout_s_raw = os.getenv("ORKET_MODEL_STREAM_REAL_TIMEOUT_S", "20")
        try:
            timeout_s = float(timeout_s_raw)
        except ValueError:
            timeout_s = 60.0
        provider_name = _real_provider_name()
        if provider_name == "ollama":
            return OllamaModelStreamProvider(model_id=model_id, timeout_s=timeout_s)
        if provider_name in {"openai_compat", "lmstudio"}:
            base_url = _openai_base_url()
            if not base_url:
                raise ValueError(
                    "ORKET_MODEL_STREAM_REAL_PROVIDER=openai_compat requires ORKET_MODEL_STREAM_OPENAI_BASE_URL."
                )
            api_key = str(os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY", "")).strip() or None
            return OpenAICompatModelStreamProvider(
                model_id=model_id,
                base_url=base_url,
                api_key=api_key,
                timeout_s=timeout_s,
            )
        raise ValueError(
            f"Unsupported ORKET_MODEL_STREAM_REAL_PROVIDER='{provider_name}'. "
            "Expected: ollama|openai_compat|lmstudio."
        )
    raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")


def validate_model_stream_v1_start(*, input_config: dict[str, Any], turn_params: dict[str, Any]) -> None:
    # Build-time validation is used by the API for fail-fast diagnostics before turn execution.
    _build_provider(input_config=input_config, turn_params=turn_params)


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
    provider = _build_provider(input_config=input_config, turn_params=turn_params)
    req = ProviderTurnRequest(input_config=input_config, turn_params=turn_params)
    provider_turn_id: str | None = None
    stop_reason = ""
    provider_error = ""

    async def _cancel_watch() -> None:
        await interaction_context.await_cancel()
        if provider_turn_id:
            await provider.cancel(provider_turn_id)

    cancel_task = asyncio.create_task(_cancel_watch())
    try:
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
