from __future__ import annotations

import asyncio
import os
from typing import Any

from orket.streaming.contracts import CommitIntent, StreamEventType
from orket.streaming.manager import InteractionContext
from orket.streaming.model_provider import ProviderEvent, ProviderEventType, ProviderTurnRequest, StubModelStreamProvider


def _provider_mode() -> str:
    return str(os.getenv("ORKET_MODEL_STREAM_PROVIDER", "stub") or "stub").strip().lower()


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
    mode = _provider_mode()
    if mode == "real":
        raise ValueError("ORKET_MODEL_STREAM_PROVIDER=real is not available yet.")
    if mode != "stub":
        raise ValueError(f"Unsupported ORKET_MODEL_STREAM_PROVIDER='{mode}'. Expected: stub|real.")

    provider = StubModelStreamProvider()
    req = ProviderTurnRequest(input_config=input_config, turn_params=turn_params)
    provider_turn_id: str | None = None

    async def _cancel_watch() -> None:
        await interaction_context.await_cancel()
        if provider_turn_id:
            await provider.cancel(provider_turn_id)

    cancel_task = asyncio.create_task(_cancel_watch())
    try:
        async for provider_event in provider.start_turn(req):
            provider_turn_id = provider_event.provider_turn_id
            stream_mapping, payload = _event_mapping(provider_event)
            if stream_mapping is None:
                if provider_event.event_type in {ProviderEventType.STOPPED, ProviderEventType.ERROR}:
                    break
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

    if interaction_context.is_canceled():
        return {"post_finalize_wait_ms": 0}
    await interaction_context.request_commit(CommitIntent(type="turn_finalize", ref="model_stream_v1"))
    return {"post_finalize_wait_ms": 0}
