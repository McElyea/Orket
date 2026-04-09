from __future__ import annotations

import asyncio
import inspect
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
import ollama

from orket.adapters.llm.local_model_provider_runtime_target import (
    ensure_provider_runtime_target,
    provider_runtime_target_payload,
)
from orket.adapters.llm.local_prompting_policy import LocalPromptingPolicyResult, resolve_local_prompting_policy
from orket.adapters.llm.openai_compat_runtime import (
    build_orket_session_id,
    build_prompt_fingerprint,
    extract_openai_content,
    extract_openai_timings,
    extract_openai_tool_calls,
    extract_openai_usage,
    normalize_openai_base_url,
    select_response_headers,
    validate_openai_messages,
)
from orket.adapters.llm.openai_native_tools import build_openai_native_tooling
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket.logging import log_event
from orket.runtime.provider_runtime_target import ProviderRuntimeTarget


@dataclass
class ModelResponse:
    content: str
    raw: dict[str, Any]


def _read_provider_env() -> str:
    return str(os.getenv("ORKET_LLM_PROVIDER") or os.getenv("ORKET_MODEL_PROVIDER") or "ollama").strip().lower()


def _map_provider_backend(raw: str) -> str:
    if raw in {"openai_compat", "lmstudio"}:
        return "openai_compat"
    return "ollama"


def _map_provider_name(raw: str) -> str:
    if raw == "lmstudio":
        return "lmstudio"
    if raw == "openai_compat":
        return "openai_compat"
    return "ollama"


class LocalModelProvider:
    """Asynchronous local model provider for ollama and openai-compatible backends."""

    def __init__(
        self,
        model: str,
        temperature: float = 0.2,
        seed: int | None = None,
        timeout: int = 300,
        *,
        provider: str = "",
        base_url: str = "",
        api_key: str = "",
        connect_timeout_seconds: float = 30.0,
    ):
        """Initialize provider.

        `timeout` is the total response generation timeout in seconds.
        `connect_timeout_seconds` is the TCP connection establishment timeout in seconds.
        """
        self.requested_model = str(model or "").strip()
        self.model = self.requested_model
        self.temperature = self._resolve_temperature_override(temperature)
        self.seed = self._resolve_seed_override(seed)
        resolved_timeout = float(timeout)
        resolved_connect_timeout = max(1.0, float(connect_timeout_seconds))
        if resolved_timeout < resolved_connect_timeout:
            raise ValueError("timeout must be greater than or equal to connect_timeout_seconds")
        self.timeout = timeout
        self.connect_timeout_seconds = resolved_connect_timeout
        self._provider_override = str(provider or "").strip().lower()
        self._base_url_override = str(base_url or "").strip()
        self._api_key_override = str(api_key or "").strip()
        provider_env = self._provider_override or _read_provider_env()
        self.provider_backend = _map_provider_backend(provider_env)
        self.provider_name = _map_provider_name(provider_env)
        self.openai_base_url = self._resolve_openai_base_url()
        self.openai_api_key = self._resolve_openai_api_key()
        self.ollama_host = self._resolve_ollama_host()
        self.client: Any

        if self.provider_backend == "openai_compat":
            self.client = httpx.AsyncClient(
                base_url=self.openai_base_url,
                timeout=httpx.Timeout(
                    connect=self.connect_timeout_seconds,
                    read=max(1.0, float(self.timeout)),
                    write=30.0,
                    pool=10.0,
                ),
            )
        else:
            self.client = ollama.AsyncClient(host=self.ollama_host) if self.ollama_host else ollama.AsyncClient()
        self._provider_managed_client_id = id(self.client)
        self._closed = False
        self._openai_session_epoch = 0
        self._seen_context_epochs: set[int] = set()
        self._runtime_target: ProviderRuntimeTarget | None = None

    @staticmethod
    def _resolve_temperature_override(default_temperature: float) -> float:
        for key in ("ORKET_BENCH_TEMPERATURE", "ORKET_LLM_TEMPERATURE", "ORKET_MODEL_TEMPERATURE"):
            raw = str(os.getenv(key, "")).strip()
            if not raw:
                continue
            try:
                return float(raw)
            except ValueError:
                continue
        return float(default_temperature)

    @staticmethod
    def _resolve_seed_override(default_seed: int | None) -> int | None:
        if isinstance(default_seed, int):
            return default_seed
        for key in ("ORKET_BENCH_SEED", "ORKET_LLM_SEED", "ORKET_MODEL_SEED"):
            raw = str(os.getenv(key, "")).strip()
            if not raw:
                continue
            try:
                parsed = int(raw)
            except ValueError:
                continue
            if parsed > 0:
                return parsed
        return default_seed

    @staticmethod
    def _ns_to_ms(value: Any) -> float | None:
        if not isinstance(value, (int, float)):
            return None
        return float(value) / 1_000_000.0

    @staticmethod
    def _native_tool_names(native_tools: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for tool in native_tools:
            if not isinstance(tool, dict):
                continue
            function_payload = tool.get("function")
            if not isinstance(function_payload, dict):
                continue
            name = str(function_payload.get("name") or "").strip()
            if name:
                names.append(name)
        return names

    @staticmethod
    def _normalize_ollama_tool_calls(tool_calls: Any) -> list[dict[str, Any]]:
        if not isinstance(tool_calls, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in tool_calls:
            if isinstance(item, dict):
                function_payload = item.get("function")
                if not isinstance(function_payload, dict):
                    continue
                function_name = str(function_payload.get("name") or "").strip()
                if not function_name:
                    continue
                payload: dict[str, Any] = {
                    "type": str(item.get("type") or "function"),
                    "function": {
                        "name": function_name,
                        "arguments": function_payload.get("arguments"),
                    },
                }
                call_id = str(item.get("id") or "").strip()
                if call_id:
                    payload["id"] = call_id
                normalized.append(payload)
                continue

            function_payload = getattr(item, "function", None)
            function_name = str(getattr(function_payload, "name", "") or "").strip()
            if not function_name:
                continue
            normalized.append(
                {
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": getattr(function_payload, "arguments", None),
                    },
                }
            )
        return normalized

    def _resolve_request_session_id(self, base_session_id: str) -> str:
        if self.provider_backend != "openai_compat":
            return base_session_id
        epoch = max(0, int(getattr(self, "_openai_session_epoch", 0) or 0))
        if epoch == 0:
            return base_session_id
        return f"{base_session_id}-ctx{epoch}"

    def _context_reset_status(self, *, provider_session_epoch: int) -> str:
        if self.provider_backend != "openai_compat":
            return "stateless_backend"
        if int(provider_session_epoch) in self._seen_context_epochs:
            return "context_unknown"
        return "fresh_context"

    def _resolve_provider_backend(self) -> str:
        return _map_provider_backend(self._provider_override or _read_provider_env())

    def _resolve_provider_name(self) -> str:
        return _map_provider_name(self._provider_override or _read_provider_env())

    def _resolve_openai_base_url(self) -> str:
        if self._base_url_override:
            return normalize_openai_base_url(self._base_url_override, default="http://127.0.0.1:1234/v1")
        raw = str(
            os.getenv("ORKET_LLM_OPENAI_BASE_URL")
            or os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL")
            or "http://127.0.0.1:1234/v1"
        ).strip()
        return normalize_openai_base_url(raw, default="http://127.0.0.1:1234/v1")

    def _resolve_openai_api_key(self) -> str:
        if self._api_key_override:
            return self._api_key_override
        return str(
            os.getenv("ORKET_LLM_OPENAI_API_KEY") or os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY") or ""
        ).strip()

    def _resolve_ollama_host(self) -> str:
        if self._base_url_override:
            return self._base_url_override
        return str(os.getenv("ORKET_LLM_OLLAMA_HOST") or os.getenv("OLLAMA_HOST") or "").strip()

    async def complete(
        self,
        messages: list[dict[str, str]],
        runtime_context: dict[str, Any] | None = None,
    ) -> ModelResponse:
        resolved_context = dict(runtime_context or {})
        effective_model = await ensure_provider_runtime_target(self)
        policy = await resolve_local_prompting_policy(
            provider_backend=self.provider_backend,
            model=effective_model,
            messages=list(messages),
            runtime_context=resolved_context,
        )
        native_tools, native_tool_choice, native_payload_overrides = build_openai_native_tooling(
            model=self.model,
            runtime_context=resolved_context,
        )
        if self.provider_backend == "openai_compat":
            return await self._complete_openai_compat(
                policy.messages,
                policy,
                runtime_context=resolved_context,
                native_tools=native_tools,
                native_tool_choice=native_tool_choice,
                native_payload_overrides=native_payload_overrides,
            )
        return await self._complete_ollama(
            policy.messages,
            policy,
            native_tools=native_tools,
            native_tool_choice=native_tool_choice,
            native_payload_overrides=native_payload_overrides,
        )

    async def _complete_ollama(
        self,
        messages: list[dict[str, str]],
        local_prompting_policy: LocalPromptingPolicyResult,
        *,
        native_tools: list[dict[str, Any]],
        native_tool_choice: str | None,
        native_payload_overrides: Mapping[str, Any],
    ) -> ModelResponse:
        options = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed
        options.update(local_prompting_policy.ollama_options_overrides())
        request_format = ""
        # Strict payload paths now use one canonical JSON object, including legacy
        # tool_call turns that carry multiple calls via {"content":"","tool_calls":[...]}.
        if local_prompting_policy.task_class in {"strict_json", "tool_call"} and not native_tools:
            request_format = "json"
        native_tool_names = self._native_tool_names(native_tools)

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                started_at = time.perf_counter()
                request_kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "options": options,
                }
                if native_tools:
                    request_kwargs["tools"] = native_tools
                if request_format:
                    request_kwargs["format"] = request_format
                response = await asyncio.wait_for(
                    self.client.chat(**request_kwargs),
                    timeout=self.timeout,
                )

                content = response.get("message", {}).get("content", "")
                tool_calls = self._normalize_ollama_tool_calls(response.get("message", {}).get("tool_calls"))
                prompt_tokens = response.get("prompt_eval_count")
                completion_tokens = response.get("eval_count")
                total_tokens = None
                if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
                    total_tokens = prompt_tokens + completion_tokens

                prompt_ms = self._ns_to_ms(response.get("prompt_eval_duration"))
                predicted_ms = self._ns_to_ms(response.get("eval_duration"))
                total_ms = self._ns_to_ms(response.get("total_duration"))

                raw = {
                    "ollama": response,
                    "tool_calls": tool_calls,
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "timings": {
                        "prompt_ms": prompt_ms,
                        "predicted_ms": predicted_ms,
                        "total_ms": total_ms,
                    },
                    "provider": "ollama-async",
                    "provider_backend": "ollama",
                    "model": self.model,
                    "requested_model": self.requested_model,
                    "provider_session_epoch": None,
                    "context_reset_status": "stateless_backend",
                    "retries": attempt,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "response_chars": len(content),
                    "ollama_request_format": request_format or None,
                    "ollama_format_fallback_used": False,
                    "ollama_native_tool_names": native_tool_names,
                    "ollama_tool_choice_requested": native_tool_choice,
                    "ollama_native_payload_overrides": dict(native_payload_overrides),
                    "runtime_target": provider_runtime_target_payload(self),
                }
                raw.update(local_prompting_policy.telemetry())
                return ModelResponse(content=content, raw=raw)

            except TypeError as exc:
                if native_tools and "tools" in str(exc):
                    raise ModelProviderError(
                        f"Ollama client does not support native tools for model {self.model}."
                    ) from exc
                if request_format and "format" in str(exc):
                    raise ModelProviderError(
                        "Ollama client does not support format='json' for strict task "
                        f"class '{local_prompting_policy.task_class}'."
                    ) from exc
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(exc)}") from exc
            except (TimeoutError, ModelTimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.") from exc
                log_event(
                    "model_timeout_retry",
                    {"model": self.model, "attempt": attempt + 1, "retry_delay_sec": retry_delay},
                )
            except (ConnectionError, ollama.ResponseError, ModelConnectionError) as exc:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(
                        f"Ollama connection failed after {max_retries} attempts: {str(exc)}"
                    ) from exc
                log_event(
                    "model_connection_retry",
                    {
                        "model": self.model,
                        "attempt": attempt + 1,
                        "retry_delay_sec": retry_delay,
                        "error": str(exc),
                    },
                )
            except asyncio.CancelledError:
                raise
            except (RuntimeError, ValueError, KeyError, AttributeError, OSError) as exc:
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(exc)}") from exc

            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        raise ModelProviderError(f"Unexpected error invoking model {self.model}: retry loop exited without response.")

    async def _complete_openai_compat(
        self,
        messages: list[dict[str, str]],
        local_prompting_policy: LocalPromptingPolicyResult,
        *,
        runtime_context: Mapping[str, Any],
        native_tools: list[dict[str, Any]],
        native_tool_choice: str | None,
        native_payload_overrides: Mapping[str, Any],
    ) -> ModelResponse:
        invalid_roles = validate_openai_messages(list(messages))
        if invalid_roles:
            raise ModelProviderError(
                "OpenAI-compatible messages require roles in "
                "[assistant, system, tool, user]. "
                f"Invalid message roles: {', '.join(invalid_roles[:8])}. Normalize upstream."
            )
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "stream": False,
        }
        payload.update(local_prompting_policy.openai_payload_overrides())
        if self.seed is not None:
            payload["seed"] = self.seed
        response_format = str(os.getenv("ORKET_LLM_OPENAI_RESPONSE_FORMAT", "")).strip().lower()
        if response_format in {"text", "json_schema"}:
            payload["response_format"] = {"type": response_format}
        if native_tools:
            payload["tools"] = native_tools
        if native_tool_choice:
            payload["tool_choice"] = native_tool_choice
        payload.update(native_payload_overrides)
        base_session_id = build_orket_session_id(
            runtime_context=runtime_context,
            model=self.model,
            provider_name=self.provider_name,
            fallback_messages=list(messages),
            preferred_session_id=str(local_prompting_policy.lmstudio_session_id or ""),
        )
        orket_session_id = self._resolve_request_session_id(base_session_id)
        orket_session_epoch = max(0, int(getattr(self, "_openai_session_epoch", 0) or 0))
        context_reset_status = self._context_reset_status(provider_session_epoch=orket_session_epoch)
        orket_request_id = f"orket-{time.time_ns()}"
        prompt_fingerprint = build_prompt_fingerprint(payload)

        headers = {"Content-Type": "application/json"}
        if self.openai_api_key:
            headers["Authorization"] = f"Bearer {self.openai_api_key}"
        headers["X-Orket-Session-Id"] = orket_session_id
        headers["X-Client-Session"] = orket_session_id
        headers["X-Orket-Request-Id"] = orket_request_id

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                started_at = time.perf_counter()
                response = await asyncio.wait_for(
                    self.client.post("/chat/completions", headers=headers, json=payload),
                    timeout=self.timeout,
                )
                response.raise_for_status()
                parsed = response.json()
                if not isinstance(parsed, dict):
                    raise ValueError("OpenAI-compatible response must be a JSON object.")
                content = extract_openai_content(parsed)
                tool_calls = extract_openai_tool_calls(parsed)
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                prompt_tokens, completion_tokens, total_tokens = extract_openai_usage(parsed)
                prompt_ms, predicted_ms, total_ms = extract_openai_timings(parsed, latency_ms)
                outbound_role_sequence = [
                    str(message.get("role") or "").strip().lower()
                    for message in messages
                    if isinstance(message, dict)
                ]
                outbound_role_counts = {
                    role: outbound_role_sequence.count(role)
                    for role in sorted(set(outbound_role_sequence))
                }

                raw = {
                    "openai_compat": parsed,
                    "tool_calls": tool_calls,
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "usage": {
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": total_tokens,
                    },
                    "timings": {
                        "prompt_ms": prompt_ms,
                        "predicted_ms": predicted_ms,
                        "total_ms": total_ms,
                    },
                    "provider": "openai-compat",
                    "provider_backend": self.provider_backend,
                    "provider_name": self.provider_name,
                    "base_url": self.openai_base_url,
                    "model": self.model,
                    "requested_model": self.requested_model,
                    "provider_session_epoch": orket_session_epoch,
                    "context_reset_status": context_reset_status,
                    "retries": attempt,
                    "latency_ms": latency_ms,
                    "response_chars": len(content),
                    "orket_session_id": orket_session_id,
                    "orket_session_epoch": orket_session_epoch,
                    "orket_request_id": orket_request_id,
                    "prompt_fingerprint": prompt_fingerprint,
                    "orket_trace": {
                        "provider_backend": self.provider_backend,
                        "provider_name": self.provider_name,
                    },
                    "http": {
                        "status_code": int(response.status_code),
                        "response_headers": select_response_headers(response.headers),
                    },
                    "runtime_target": provider_runtime_target_payload(self),
                    "openai_request_message_count": len(messages),
                    "openai_request_role_sequence": outbound_role_sequence,
                    "openai_request_role_counts": outbound_role_counts,
                    "openai_native_tool_names": [
                        str((tool.get("function") or {}).get("name") or "").strip()
                        for tool in native_tools
                        if isinstance(tool, dict)
                    ],
                    "openai_tool_choice": native_tool_choice,
                    "openai_native_payload_overrides": dict(native_payload_overrides),
                }
                raw.update(local_prompting_policy.telemetry())
                self._seen_context_epochs.add(orket_session_epoch)
                return ModelResponse(content=content, raw=raw)

            except (TimeoutError, httpx.TimeoutException, ModelTimeoutError) as exc:
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.") from exc
                log_event(
                    "model_timeout_retry",
                    {"model": self.model, "attempt": attempt + 1, "retry_delay_sec": retry_delay},
                )
            except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError, ModelConnectionError) as exc:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(
                        f"OpenAI-compatible connection failed after {max_retries} attempts: {str(exc)}"
                    ) from exc
                log_event(
                    "model_connection_retry",
                    {
                        "model": self.model,
                        "attempt": attempt + 1,
                        "retry_delay_sec": retry_delay,
                        "error": str(exc),
                    },
                )
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code if e.response is not None else "unknown"
                detail = str(e.response.text or "").strip()[:400] if e.response is not None else str(e)
                raise ModelProviderError(
                    f"OpenAI-compatible request failed status={status_code} model={self.model}: {detail}"
                ) from e
            except asyncio.CancelledError:
                raise
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, httpx.HTTPError) as exc:
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(exc)}") from exc

            await asyncio.sleep(retry_delay)
            retry_delay *= 2
        raise ModelProviderError(f"Unexpected error invoking model {self.model}: retry loop exited without response.")

    async def clear_context(self) -> None:
        """Rotate context for stateful OpenAI-compatible backends; stateless backends remain no-op."""
        if str(getattr(self, "provider_backend", "") or "") == "openai_compat":
            self._openai_session_epoch = max(0, int(getattr(self, "_openai_session_epoch", 0) or 0)) + 1

    async def __aenter__(self) -> LocalModelProvider:
        return self

    async def close(self) -> None:
        if bool(getattr(self, "_closed", False)):
            return
        client = getattr(self, "client", None)
        close_method = None
        if client is not None:
            close_method = getattr(client, "aclose", None) or getattr(client, "close", None)
        if callable(close_method):
            maybe_awaitable = close_method()
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        self._closed = True

    async def aclose(self) -> None:
        await self.close()

    async def __aexit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        _ = (exc_type, exc, traceback)
        await self.close()
