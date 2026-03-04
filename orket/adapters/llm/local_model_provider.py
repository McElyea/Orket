from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
import ollama

from orket.exceptions import ModelConnectionError, ModelProviderError, ModelTimeoutError
from orket.logging import log_event


@dataclass
class ModelResponse:
    content: str
    raw: Dict[str, Any]


class LocalModelProvider:
    """
    Asynchronous local model provider.
    Supported backends:
    - ollama (default)
    - openai_compat / lmstudio (via ORKET_LLM_PROVIDER)
    """

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

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if isinstance(value, int):
            return value
        if isinstance(value, float) and float(value).is_integer():
            return int(value)
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            token = value.strip()
            try:
                return float(token)
            except ValueError:
                return None
        return None

    @staticmethod
    def _normalize_base_url(raw: str, *, default: str) -> str:
        value = str(raw or "").strip() or default
        if "://" not in value:
            value = f"http://{value}"
        parsed = urlparse(value)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid OpenAI-compatible base URL '{value}'")
        base = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")
        if path:
            return f"{base}{path}"
        return f"{base}/v1"

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
        return self._normalize_base_url(raw, default="http://127.0.0.1:1234/v1")

    @staticmethod
    def _extract_openai_content(payload: Dict[str, Any]) -> str:
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
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)
        return ""

    def _extract_openai_usage(self, payload: Dict[str, Any]) -> tuple[int | None, int | None, int | None]:
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        prompt_tokens = self._to_int(usage.get("prompt_tokens"))
        completion_tokens = self._to_int(usage.get("completion_tokens"))
        total_tokens = self._to_int(usage.get("total_tokens"))
        if total_tokens is None and isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total_tokens = prompt_tokens + completion_tokens
        return prompt_tokens, completion_tokens, total_tokens

    def _extract_openai_timings(self, payload: Dict[str, Any], latency_ms: int) -> tuple[float, float, float]:
        timings = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}

        prompt_ms = self._to_float(timings.get("prompt_ms"))
        predicted_ms = self._to_float(timings.get("predicted_ms"))
        total_ms = self._to_float(timings.get("total_ms"))

        if prompt_ms is None:
            prompt_ms = self._ns_to_ms(timings.get("prompt_eval_duration"))
        if predicted_ms is None:
            predicted_ms = self._ns_to_ms(timings.get("eval_duration"))
        if total_ms is None:
            total_ms = self._ns_to_ms(timings.get("total_duration"))

        if prompt_ms is None:
            prompt_ms = self._ns_to_ms(payload.get("prompt_eval_duration"))
        if predicted_ms is None:
            predicted_ms = self._ns_to_ms(payload.get("eval_duration"))
        if total_ms is None:
            total_ms = self._ns_to_ms(payload.get("total_duration"))

        if total_ms is None:
            total_ms = float(latency_ms)

        if prompt_ms is None and predicted_ms is None:
            prompt_ms = 0.0
            predicted_ms = float(total_ms)
        elif prompt_ms is None:
            prompt_ms = max(0.0, float(total_ms) - float(predicted_ms or 0.0))
        elif predicted_ms is None:
            predicted_ms = max(0.0, float(total_ms) - float(prompt_ms or 0.0))

        return float(prompt_ms), float(predicted_ms), float(total_ms)

    @staticmethod
    def _validate_openai_messages(messages: List[Dict[str, Any]]) -> None:
        allowed_roles = {"system", "user", "assistant", "tool"}
        invalid: list[str] = []
        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                invalid.append(f"{index}:<non-object>")
                continue
            role = str(message.get("role") or "").strip().lower()
            if role not in allowed_roles:
                invalid.append(f"{index}:{role or '<missing>'}")
        if invalid:
            allowed = ", ".join(sorted(allowed_roles))
            details = ", ".join(invalid[:8])
            raise ModelProviderError(
                "OpenAI-compatible messages require roles in "
                f"[{allowed}]. Invalid message roles: {details}. Normalize upstream."
            )

    async def complete(self, messages: List[Dict[str, str]]) -> ModelResponse:
        if self.provider_backend == "openai_compat":
            return await self._complete_openai_compat(messages)
        return await self._complete_ollama(messages)

    async def _complete_ollama(self, messages: List[Dict[str, str]]) -> ModelResponse:
        options = {"temperature": self.temperature}
        if self.seed is not None:
            options["seed"] = self.seed

        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                started_at = time.perf_counter()
                response = await asyncio.wait_for(
                    self.client.chat(model=self.model, messages=messages, options=options),
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
                }
                return ModelResponse(content=content, raw=raw)

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

    async def _complete_openai_compat(self, messages: List[Dict[str, str]]) -> ModelResponse:
        self._validate_openai_messages(list(messages))
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": list(messages),
            "temperature": self.temperature,
            "stream": False,
        }
        if self.seed is not None:
            payload["seed"] = self.seed
        response_format = str(os.getenv("ORKET_LLM_OPENAI_RESPONSE_FORMAT", "")).strip().lower()
        if response_format in {"text", "json_schema"}:
            payload["response_format"] = {"type": response_format}

        headers = {"Content-Type": "application/json"}
        if self.openai_api_key:
            headers["Authorization"] = f"Bearer {self.openai_api_key}"

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
                content = self._extract_openai_content(parsed)
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                prompt_tokens, completion_tokens, total_tokens = self._extract_openai_usage(parsed)
                prompt_ms, predicted_ms, total_ms = self._extract_openai_timings(parsed, latency_ms)

                raw = {
                    "openai_compat": parsed,
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
                }
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
