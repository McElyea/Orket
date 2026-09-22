from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from orket.adapters.llm.openai_compat_runtime import (
    extract_openai_content,
    extract_openai_timings,
    extract_openai_tool_calls,
    extract_openai_usage,
)
from orket.core.contracts.model_timing import nanoseconds_to_ms

side_effecting = False


class ProviderExtractor(Protocol):
    def extract_content(self, payload: Any) -> str | None: ...

    def extract_tool_calls(self, payload: Any) -> list[dict[str, Any]]: ...

    def extract_usage(self, payload: Any) -> tuple[int | None, int | None, int | None]: ...

    def extract_timings(self, payload: Any, latency_ms: int) -> tuple[float | None, float | None, float | None]: ...


class OpenAIExtractor:
    def extract_content(self, payload: Any) -> str | None:
        return extract_openai_content(dict(payload)) if isinstance(payload, Mapping) else None

    def extract_tool_calls(self, payload: Any) -> list[dict[str, Any]]:
        return extract_openai_tool_calls(dict(payload)) if isinstance(payload, Mapping) else []

    def extract_usage(self, payload: Any) -> tuple[int | None, int | None, int | None]:
        return extract_openai_usage(dict(payload)) if isinstance(payload, Mapping) else (None, None, None)

    def extract_timings(self, payload: Any, latency_ms: int) -> tuple[float | None, float | None, float | None]:
        return extract_openai_timings(dict(payload), latency_ms) if isinstance(payload, Mapping) else (None, None, None)


class OllamaExtractor:
    def extract_content(self, payload: Any) -> str | None:
        message = _get_value(payload, "message")
        if message is None:
            return None
        content = _get_value(message, "content")
        if content is None:
            return ""
        return content if isinstance(content, str) else None

    def extract_tool_calls(self, payload: Any) -> list[dict[str, Any]]:
        message = _get_value(payload, "message")
        if message is None:
            return []
        raw_tool_calls = _get_value(message, "tool_calls")
        if not isinstance(raw_tool_calls, list):
            return []
        normalized: list[dict[str, Any]] = []
        for item in raw_tool_calls:
            if isinstance(item, Mapping):
                function_payload = item.get("function")
                if not isinstance(function_payload, Mapping):
                    continue
                function_name = str(function_payload.get("name") or "").strip()
                if not function_name:
                    continue
                payload_item: dict[str, Any] = {
                    "type": str(item.get("type") or "function"),
                    "function": {
                        "name": function_name,
                        "arguments": function_payload.get("arguments"),
                    },
                }
                call_id = str(item.get("id") or "").strip()
                if call_id:
                    payload_item["id"] = call_id
                normalized.append(payload_item)
                continue

            function_payload = _get_value(item, "function")
            function_name = str(_get_value(function_payload, "name") or "").strip()
            if not function_name:
                continue
            normalized.append(
                {
                    "type": "function",
                    "function": {
                        "name": function_name,
                        "arguments": _get_value(function_payload, "arguments"),
                    },
                }
            )
        return normalized

    def extract_usage(self, payload: Any) -> tuple[int | None, int | None, int | None]:
        prompt_tokens = _get_value(payload, "prompt_eval_count")
        completion_tokens = _get_value(payload, "eval_count")
        prompt = prompt_tokens if isinstance(prompt_tokens, int) else None
        completion = completion_tokens if isinstance(completion_tokens, int) else None
        total = prompt + completion if isinstance(prompt, int) and isinstance(completion, int) else None
        return prompt, completion, total

    def extract_timings(self, payload: Any, latency_ms: int) -> tuple[float | None, float | None, float | None]:
        del latency_ms  # Client elapsed time cannot establish a backend phase duration.
        return (nanoseconds_to_ms(_get_value(payload, "prompt_eval_duration")),
                nanoseconds_to_ms(_get_value(payload, "eval_duration")),
                nanoseconds_to_ms(_get_value(payload, "total_duration")))


def _get_value(payload: Any, key: str) -> Any:
    if isinstance(payload, Mapping):
        return payload.get(key)
    return getattr(payload, key, None)


PROVIDER_EXTRACTORS: dict[str, ProviderExtractor] = {
    "openai": OpenAIExtractor(),
    "openai_compat": OpenAIExtractor(),
    "lmstudio": OpenAIExtractor(),
    "llama_cpp": OpenAIExtractor(),
    "ollama": OllamaExtractor(),
}


def extractor_for_provider(provider: str) -> ProviderExtractor:
    key = str(provider or "").strip().lower()
    if key not in PROVIDER_EXTRACTORS:
        raise KeyError(f"Unsupported provider extractor '{provider}'")
    return PROVIDER_EXTRACTORS[key]


__all__ = [
    "OllamaExtractor",
    "OpenAIExtractor",
    "PROVIDER_EXTRACTORS",
    "ProviderExtractor",
    "extractor_for_provider",
]
