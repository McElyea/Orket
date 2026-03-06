from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import httpx
import ollama

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
from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket.logging import log_event


@dataclass
class ModelResponse:
    content: str
    raw: Dict[str, Any]


class LocalModelProvider:
    """Asynchronous local model provider for ollama and openai-compatible backends."""

    def __init__(self, model: str, temperature: float = 0.2, seed: Optional[int] = None, timeout: int = 300):
        self.model = model
        self.temperature = self._resolve_temperature_override(temperature)
        self.seed = self._resolve_seed_override(seed)
        self.timeout = timeout
        self.provider_backend = self._resolve_provider_backend()
        self.provider_name = self._resolve_provider_name()
        self.openai_base_url = self._resolve_openai_base_url()
        self.openai_api_key = str(
            os.getenv("ORKET_LLM_OPENAI_API_KEY")
            or os.getenv("ORKET_MODEL_STREAM_OPENAI_API_KEY")
            or ""
        ).strip()
        self.ollama_host = str(
            os.getenv("ORKET_LLM_OLLAMA_HOST")
            or os.getenv("OLLAMA_HOST")
            or ""
        ).strip()

        if self.provider_backend == "openai_compat":
            self.client = httpx.AsyncClient(
                base_url=self.openai_base_url,
                timeout=httpx.Timeout(timeout=max(1.0, float(self.timeout))),
            )
        else:
            self.client = ollama.AsyncClient(host=self.ollama_host) if self.ollama_host else ollama.AsyncClient()

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
    def _resolve_seed_override(default_seed: Optional[int]) -> Optional[int]:
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

    def _resolve_provider_backend(self) -> str:
        raw = str(
            os.getenv("ORKET_LLM_PROVIDER")
            or os.getenv("ORKET_MODEL_PROVIDER")
            or "ollama"
        ).strip().lower()
        if raw in {"openai_compat", "lmstudio"}:
            return "openai_compat"
        return "ollama"

    def _resolve_provider_name(self) -> str:
        raw = str(
            os.getenv("ORKET_LLM_PROVIDER")
            or os.getenv("ORKET_MODEL_PROVIDER")
            or "ollama"
        ).strip().lower()
        if raw == "lmstudio":
            return "lmstudio"
        if raw == "openai_compat":
            return "openai_compat"
        return "ollama"

    def _resolve_openai_base_url(self) -> str:
        raw = str(
            os.getenv("ORKET_LLM_OPENAI_BASE_URL")
            or os.getenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL")
            or "http://127.0.0.1:1234/v1"
        ).strip()
        return normalize_openai_base_url(raw, default="http://127.0.0.1:1234/v1")

    async def complete(
        self,
        messages: List[Dict[str, str]],
        runtime_context: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        resolved_context = dict(runtime_context or {})
        policy = await resolve_local_prompting_policy(
            provider_backend=self.provider_backend,
            model=self.model,
            messages=list(messages),
            runtime_context=resolved_context,
        )
        if self.provider_backend == "openai_compat":
            return await self._complete_openai_compat(
                policy.messages,
                policy,
                runtime_context=resolved_context,
            )
        return await self._complete_ollama(policy.messages, policy)

    async def _complete_ollama(
        self,
        messages: List[Dict[str, str]],
        local_prompting_policy: LocalPromptingPolicyResult,
    ) -> ModelResponse:
        options = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed
        options.update(local_prompting_policy.ollama_options_overrides())
        request_format = ""
        format_fallback_used = False
        if local_prompting_policy.task_class in {"strict_json", "tool_call"}:
            request_format = "json"

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                started_at = time.perf_counter()
                request_kwargs: Dict[str, Any] = {
                    "model": self.model,
                    "messages": messages,
                    "options": options,
                }
                if request_format:
                    request_kwargs["format"] = request_format
                response = await asyncio.wait_for(
                    self.client.chat(**request_kwargs),
                    timeout=self.timeout,
                )

                content = response.get("message", {}).get("content", "")
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
                    "retries": attempt,
                    "latency_ms": int((time.perf_counter() - started_at) * 1000),
                    "response_chars": len(content),
                    "ollama_request_format": request_format or None,
                    "ollama_format_fallback_used": format_fallback_used,
                }
                raw.update(local_prompting_policy.telemetry())
                return ModelResponse(content=content, raw=raw)

            except TypeError as exc:
                # Older client shims may not accept the optional `format` keyword.
                if request_format and "format" in str(exc):
                    format_fallback_used = True
                    request_format = ""
                    continue
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(exc)}") from exc
            except (asyncio.TimeoutError, ModelTimeoutError):
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.")
                log_event(
                    "model_timeout_retry",
                    {"model": self.model, "attempt": attempt + 1, "retry_delay_sec": retry_delay},
                )
            except (ConnectionError, ollama.ResponseError, ModelConnectionError) as e:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(f"Ollama connection failed after {max_retries} attempts: {str(e)}")
                log_event(
                    "model_connection_retry",
                    {
                        "model": self.model,
                        "attempt": attempt + 1,
                        "retry_delay_sec": retry_delay,
                        "error": str(e),
                    },
                )
            except asyncio.CancelledError:
                raise
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError) as e:
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(e)}")

            await asyncio.sleep(retry_delay)
            retry_delay *= 2

    async def _complete_openai_compat(
        self,
        messages: List[Dict[str, str]],
        local_prompting_policy: LocalPromptingPolicyResult,
        *,
        runtime_context: Mapping[str, Any],
    ) -> ModelResponse:
        invalid_roles = validate_openai_messages(list(messages))
        if invalid_roles:
            raise ModelProviderError(
                "OpenAI-compatible messages require roles in "
                "[assistant, system, tool, user]. "
                f"Invalid message roles: {', '.join(invalid_roles[:8])}. Normalize upstream."
            )
        payload: Dict[str, Any] = {
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
        orket_session_id = build_orket_session_id(
            runtime_context=runtime_context,
            model=self.model,
            provider_name=self.provider_name,
            fallback_messages=list(messages),
            preferred_session_id=str(local_prompting_policy.lmstudio_session_id or ""),
        )
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
                    "provider_backend": self.provider_name,
                    "base_url": self.openai_base_url,
                    "model": self.model,
                    "retries": attempt,
                    "latency_ms": latency_ms,
                    "response_chars": len(content),
                    "orket_session_id": orket_session_id,
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
                }
                raw.update(local_prompting_policy.telemetry())
                return ModelResponse(content=content, raw=raw)

            except (asyncio.TimeoutError, httpx.TimeoutException, ModelTimeoutError):
                if attempt == max_retries - 1:
                    raise ModelTimeoutError(f"Model {self.model} timed out after {max_retries} attempts.")
                log_event(
                    "model_timeout_retry",
                    {"model": self.model, "attempt": attempt + 1, "retry_delay_sec": retry_delay},
                )
            except (httpx.ConnectError, httpx.NetworkError, httpx.RemoteProtocolError, ModelConnectionError) as e:
                if attempt == max_retries - 1:
                    raise ModelConnectionError(
                        f"OpenAI-compatible connection failed after {max_retries} attempts: {str(e)}"
                    )
                log_event(
                    "model_connection_retry",
                    {
                        "model": self.model,
                        "attempt": attempt + 1,
                        "retry_delay_sec": retry_delay,
                        "error": str(e),
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
            except (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError, httpx.HTTPError) as e:
                raise ModelProviderError(f"Unexpected error invoking model {self.model}: {str(e)}")

            await asyncio.sleep(retry_delay)
            retry_delay *= 2

    async def clear_context(self):
        # Chat-completion calls are stateless unless explicit sessions are used.
        pass
