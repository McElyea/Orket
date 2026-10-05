from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from enum import Enum
from typing import Any

import httpx
from pydantic import BaseModel, Field

from orket.adapters.execution.owned_io import run_owned_io
from orket.core.contracts.provider_http import ModelStreamHttpPort

side_effecting = True


class ProviderEventType(str, Enum):  # noqa: UP042 - public enum representation contract
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
    def start_turn(self, req: ProviderTurnRequest) -> AsyncIterator[ProviderEvent]:
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


def _float_value(value: object) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


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
            self._canceled.setdefault(provider_turn_id, asyncio.Event())
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
            first_token_delay_ms = _int_value(req.input_config.get("first_token_delay_ms"), 0, minimum=0)
            canceled = await self._is_canceled(provider_turn_id)
            if first_token_delay_ms > 0:
                await asyncio.sleep(first_token_delay_ms / 1000.0)
                if canceled.is_set():
                    yield ProviderEvent(
                        provider_turn_id=provider_turn_id,
                        event_type=ProviderEventType.STOPPED,
                        payload={"stop_reason": "canceled"},
                    )
                    return
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


def _messages(req: ProviderTurnRequest) -> list:
    messages = req.input_config.get("messages")
    if isinstance(messages, list):
        return messages
    prompt = str(req.input_config.get("prompt") or req.input_config.get("input") or "").strip() or "Continue."
    return [{"role": "user", "content": prompt}]


def _initial_events(turn_id: str, model_id: str) -> list[ProviderEvent]:
    return [ProviderEvent(provider_turn_id=turn_id, event_type=kind, payload=payload) for kind, payload in (
        (ProviderEventType.SELECTED, {"model_id": model_id, "reason": "real_provider"}),
        (ProviderEventType.LOADING, {"cold_start": False, "progress": 0.0}),
        (ProviderEventType.READY, {"model_id": model_id, "warm_state": "unknown", "load_ms": 0}))]


# Provider failures remain advisory ERROR events; cleanup runs outside this handler.
_PROVIDER_ERRORS = (RuntimeError, ValueError, TypeError, KeyError, OSError, httpx.HTTPError)


async def _real_turn(provider, req) -> AsyncIterator[ProviderEvent]:
    turn_id = f"provider-turn-{uuid.uuid4().hex[:12]}"
    async with provider._lock:
        provider._canceled[turn_id] = asyncio.Event()
    try:
        for event in _initial_events(turn_id, provider._model_id):
            yield event
        async with provider._http.open() as (client, resources):
            tokens = provider._tokens(req, client, resources, turn_id)
            try:
                try:
                    async for event in tokens:
                        yield event
                    yield ProviderEvent(provider_turn_id=turn_id, event_type=ProviderEventType.STOPPED,
                        payload={"stop_reason": "canceled" if provider._canceled[turn_id].is_set() else "completed"})
                except _PROVIDER_ERRORS as exc:
                    yield ProviderEvent(provider_turn_id=turn_id, event_type=ProviderEventType.ERROR,
                                        payload={"error": f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__,
                                                 "error_type": type(exc).__name__})
            finally:
                await run_owned_io(tokens.aclose, label="model-stream-tokens", preserve_failure=True)
    finally:
        async with provider._lock:
            provider._canceled.pop(turn_id, None)


class OllamaModelStreamProvider(ModelStreamProvider):
    def __init__(self, *, model_id: str, base_url: str | None = None, timeout_s: float = 60.0,
                 stream_timeout_s: float | None = None, http_client_owner: ModelStreamHttpPort) -> None:
        self._base_url = str(base_url or "").strip()
        self._model_id = model_id
        self._connect_timeout_s = max(1.0, float(timeout_s))
        budget = float(stream_timeout_s if stream_timeout_s is not None else float(timeout_s) * 3.0)
        if not math.isfinite(budget):
            raise ValueError("E_PROVIDER_HTTP_TIMEOUT_NOT_FINITE")
        self._stream_timeout_s = max(1.0, budget)
        self._http = http_client_owner
        self._canceled: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def start_turn(self, req: ProviderTurnRequest) -> AsyncIterator[ProviderEvent]:
        return _real_turn(self, req)

    async def _tokens(self, req, client, resources, turn_id):
        options: dict[str, Any] = {"num_predict": _int_value(req.input_config.get("max_tokens"), 64, minimum=1)}
        if "seed" in req.input_config:
            options["seed"] = _int_value(req.input_config.get("seed"), 0)
        if "temperature" in req.input_config and (temperature := _float_value(req.input_config["temperature"])) is not None:
            options["temperature"] = temperature
        async with asyncio.timeout(self._connect_timeout_s):
            stream = await client.chat(model=self._model_id, messages=_messages(req), options=options, stream=True)
            resources.retain(stream)
        index = 0
        async with asyncio.timeout(self._stream_timeout_s):
            async for chunk in stream:
                if self._canceled[turn_id].is_set():
                    return
                delta = self._extract_delta(chunk)
                if delta:
                    yield ProviderEvent(provider_turn_id=turn_id, event_type=ProviderEventType.TOKEN_DELTA,
                                        payload={"delta": delta, "index": index})
                    index += 1

    async def cancel(self, provider_turn_id: str) -> None:
        canceled = await self._is_canceled(provider_turn_id)
        canceled.set()

    async def health(self) -> dict[str, Any]:
        return {"ok": True, "provider": "ollama", "model_id": self._model_id, "base_url": self._base_url or None}

    async def _is_canceled(self, provider_turn_id: str) -> asyncio.Event:
        async with self._lock:
            return self._canceled.setdefault(provider_turn_id, asyncio.Event())

    @staticmethod
    def _extract_delta(chunk: Any) -> str:
        if isinstance(chunk, dict):
            message = chunk.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content
            response = chunk.get("response")
            if isinstance(response, str):
                return response
            return ""
        message_obj = getattr(chunk, "message", None)
        content_obj = getattr(message_obj, "content", None)
        if isinstance(content_obj, str):
            return content_obj
        response_obj = getattr(chunk, "response", None)
        if isinstance(response_obj, str):
            return response_obj
        return ""


class OpenAICompatModelStreamProvider(ModelStreamProvider):
    def __init__(self, *, model_id: str, base_url: str, api_key: str | None = None, timeout_s: float = 60.0,
                 provider_name: str = "openai_compat", http_client_owner: ModelStreamHttpPort) -> None:
        self._model_id, self._base_url = model_id, base_url.rstrip("/")
        self._api_key, self._provider_name = api_key or "", provider_name
        self._timeout_s = max(1.0, float(timeout_s))
        self._http = http_client_owner
        self._canceled: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    def start_turn(self, req: ProviderTurnRequest) -> AsyncIterator[ProviderEvent]:
        return _real_turn(self, req)

    async def _tokens(self, req, client, resources, turn_id):
        if self._canceled[turn_id].is_set():
            return
        payload = {"model": self._model_id, "messages": _messages(req),
                   "max_tokens": _int_value(req.input_config.get("max_tokens"), 64, minimum=1),
                   "stream": self._http.use_stream}
        if "temperature" in req.input_config and (temperature := _float_value(req.input_config["temperature"])) is not None:
            payload["temperature"] = temperature
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        index = 0
        if self._http.use_stream:
            started = time.monotonic()
            request = client.build_request("POST", "/chat/completions", headers=headers, json=payload)
            response = await client.send(request, stream=True)
            resources.retain(response)
            response.raise_for_status()
            lines = response.aiter_lines()
            resources.retain(lines)
            async for line in lines:
                if time.monotonic() - started >= self._timeout_s:
                    raise TimeoutError(f"openai_compat stream exceeded timeout ({self._timeout_s}s) before completion")
                if self._canceled[turn_id].is_set():
                    return
                delta = self._line_delta(line)
                if delta:
                    yield ProviderEvent(provider_turn_id=turn_id, event_type=ProviderEventType.TOKEN_DELTA,
                                        payload={"delta": delta, "index": index})
                    index += 1
                    if index >= payload["max_tokens"]:
                        return
        if index == 0:
            payload["stream"] = False
            body = await self._post_chat_completion(client, headers, payload)
            text, count = self._extract_non_stream_text(body), self._extract_completion_tokens(body)
            if text or count > 0:
                token = {"delta": text, "index": index}
                if not text:
                    token.update(synthetic=True, reason="empty_content_with_completion_tokens", completion_tokens=count)
                yield ProviderEvent(provider_turn_id=turn_id, event_type=ProviderEventType.TOKEN_DELTA, payload=token)

    async def _post_chat_completion(self, client, headers, payload):
        response = await client.post("/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        parsed = response.json()
        return parsed if isinstance(parsed, dict) else {}

    def _line_delta(self, line):
        raw = line.strip()
        if not raw.startswith("data:") or not (body := raw[5:].strip()) or body == "[DONE]":
            return ""
        try:
            return self._extract_delta(json.loads(body))
        except json.JSONDecodeError:
            return ""

    async def cancel(self, provider_turn_id: str) -> None:
        canceled = await self._is_canceled(provider_turn_id)
        canceled.set()

    async def health(self) -> dict[str, Any]:
        return {"ok": True, "provider": self._provider_name, "model_id": self._model_id, "base_url": self._base_url}

    async def _is_canceled(self, provider_turn_id: str) -> asyncio.Event:
        async with self._lock:
            return self._canceled.setdefault(provider_turn_id, asyncio.Event())

    @staticmethod
    def _extract_delta(chunk: Any) -> str:
        if not isinstance(chunk, dict):
            return ""
        choices = chunk.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        delta = first.get("delta")
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                return content
            reasoning_content = delta.get("reasoning_content")
            if isinstance(reasoning_content, str):
                return reasoning_content
            text = delta.get("text")
            if isinstance(text, str):
                return text
        message = first.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content
        text = first.get("text")
        return text if isinstance(text, str) else ""

    @staticmethod
    def _extract_non_stream_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        first = choices[0]
        if not isinstance(first, dict):
            return ""
        message = first.get("message")
        if not isinstance(message, dict):
            return ""
        content = message.get("content")
        return content if isinstance(content, str) else ""

    @staticmethod
    def _extract_completion_tokens(payload: dict[str, Any]) -> int:
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            return 0
        raw = usage.get("completion_tokens")
        if isinstance(raw, int) and raw >= 0:
            return raw
        return 0
