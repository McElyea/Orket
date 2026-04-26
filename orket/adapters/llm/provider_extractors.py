from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from orket.adapters.llm.openai_compat_runtime import (
    extract_openai_content,
    extract_openai_timings,
    extract_openai_tool_calls,
    extract_openai_usage,
)


class ProviderExtractor(Protocol):
    def extract_content(self, payload: Mapping[str, Any]) -> str | None: ...

    def extract_tool_calls(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]: ...

    def extract_usage(self, payload: Mapping[str, Any]) -> tuple[int | None, int | None, int | None]: ...

    def extract_timings(self, payload: Mapping[str, Any], latency_ms: int) -> tuple[float, float, float]: ...


class OpenAIExtractor:
    def extract_content(self, payload: Mapping[str, Any]) -> str | None:
        return extract_openai_content(dict(payload))

    def extract_tool_calls(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        return extract_openai_tool_calls(dict(payload))

    def extract_usage(self, payload: Mapping[str, Any]) -> tuple[int | None, int | None, int | None]:
        return extract_openai_usage(dict(payload))

    def extract_timings(self, payload: Mapping[str, Any], latency_ms: int) -> tuple[float, float, float]:
        return extract_openai_timings(dict(payload), latency_ms)


class OllamaExtractor:
    def extract_content(self, payload: Mapping[str, Any]) -> str | None:
        message = payload.get("message")
        if not isinstance(message, Mapping):
            return None
        content = message.get("content")
        if content is None:
            return ""
        return content if isinstance(content, str) else None

    def extract_tool_calls(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        message = payload.get("message")
        if not isinstance(message, Mapping):
            return []
        raw_tool_calls = message.get("tool_calls")
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

    def extract_usage(self, payload: Mapping[str, Any]) -> tuple[int | None, int | None, int | None]:
        prompt_tokens = payload.get("prompt_eval_count")
        completion_tokens = payload.get("eval_count")
        prompt = prompt_tokens if isinstance(prompt_tokens, int) else None
        completion = completion_tokens if isinstance(completion_tokens, int) else None
        total = prompt + completion if isinstance(prompt, int) and isinstance(completion, int) else None
        return prompt, completion, total

    def extract_timings(self, payload: Mapping[str, Any], latency_ms: int) -> tuple[float, float, float]:
        prompt_ms = _ns_to_ms(payload.get("prompt_eval_duration"))
        predicted_ms = _ns_to_ms(payload.get("eval_duration"))
        total_ms = _ns_to_ms(payload.get("total_duration"))
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


def _ns_to_ms(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value) / 1_000_000.0


PROVIDER_EXTRACTORS: dict[str, ProviderExtractor] = {
    "openai": OpenAIExtractor(),
    "openai_compat": OpenAIExtractor(),
    "lmstudio": OpenAIExtractor(),
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
