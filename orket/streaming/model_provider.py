from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProviderEventType(str, Enum):
    SELECTED = "selected"
    LOADING = "loading"
    READY = "ready"
    TOKEN_DELTA = "token_delta"
    STOPPED = "stopped"
    ERROR = "error"


class ProviderEvent(BaseModel):
    provider_turn_id: str
    event_type: ProviderEventType
    payload: dict[str, Any] = Field(default_factory=dict)
    mono_ts_ms: int | None = None


class ProviderTurnRequest(BaseModel):
    input_config: dict[str, Any] = Field(default_factory=dict)
    turn_params: dict[str, Any] = Field(default_factory=dict)


class ModelStreamProvider(ABC):
    @abstractmethod
    async def start_turn(self, req: ProviderTurnRequest) -> AsyncIterator[ProviderEvent]:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, provider_turn_id: str) -> None:
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        return {"ok": True}

    async def prewarm(self, model_id: str) -> None:
        return None


def _int_value(value: Any, default: int, *, minimum: int = 0) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else minimum


def _deterministic_chunk(seed: int, index: int, chunk_size: int) -> str:
    alphabet = "abcdefghijklmnopqrstuvwxyz0123456789"
    start = (seed + index) % len(alphabet)
    chars = []
    for offset in range(chunk_size):
        chars.append(alphabet[(start + offset) % len(alphabet)])
    return "".join(chars)


class StubModelStreamProvider(ModelStreamProvider):
    def __init__(self) -> None:
        self._canceled: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def start_turn(self, req: ProviderTurnRequest) -> AsyncIterator[ProviderEvent]:
        provider_turn_id = f"provider-turn-{uuid.uuid4().hex[:12]}"
        async with self._lock:
            self._canceled[provider_turn_id] = asyncio.Event()
        try:
            seed = _int_value(req.input_config.get("seed"), 0)
            mode = str(req.input_config.get("mode") or req.turn_params.get("mode") or "basic").strip().lower()
            cold_load = bool(req.input_config.get("force_cold_model_load"))
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.SELECTED,
                payload={"model_id": "stream-test-v1", "reason": mode},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.LOADING,
                payload={"cold_start": cold_load, "progress": 0.0 if cold_load else 1.0},
            )
            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.READY,
                payload={
                    "model_id": "stream-test-v1",
                    "warm_state": "cold" if cold_load else "warm",
                    "load_ms": 120 if cold_load else 0,
                },
            )

            delta_count = _int_value(req.input_config.get("delta_count"), 1 if mode == "basic" else 512, minimum=1)
            chunk_size = _int_value(req.input_config.get("chunk_size"), 4 if mode == "basic" else 2, minimum=1)
            delay_ms = _int_value(req.input_config.get("delta_delay_ms"), 0, minimum=0)
            canceled = await self._is_canceled(provider_turn_id)
            for index in range(delta_count):
                if canceled.is_set():
                    yield ProviderEvent(
                        provider_turn_id=provider_turn_id,
                        event_type=ProviderEventType.STOPPED,
                        payload={"stop_reason": "canceled"},
                    )
                    return
                yield ProviderEvent(
                    provider_turn_id=provider_turn_id,
                    event_type=ProviderEventType.TOKEN_DELTA,
                    payload={
                        "delta": _deterministic_chunk(seed, index, chunk_size),
                        "index": index,
                    },
                )
                if delay_ms > 0:
                    await asyncio.sleep(delay_ms / 1000.0)

            yield ProviderEvent(
                provider_turn_id=provider_turn_id,
                event_type=ProviderEventType.STOPPED,
                payload={"stop_reason": "completed"},
            )
        finally:
            async with self._lock:
                self._canceled.pop(provider_turn_id, None)

    async def cancel(self, provider_turn_id: str) -> None:
        canceled = await self._is_canceled(provider_turn_id)
        canceled.set()

    async def _is_canceled(self, provider_turn_id: str) -> asyncio.Event:
        async with self._lock:
            return self._canceled.setdefault(provider_turn_id, asyncio.Event())
