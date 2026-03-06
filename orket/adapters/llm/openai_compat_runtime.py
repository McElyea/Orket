from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping
from urllib.parse import urlparse


def normalize_openai_base_url(raw: str, *, default: str) -> str:
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


def validate_openai_messages(messages: List[Dict[str, Any]]) -> list[str]:
    allowed_roles = {"system", "user", "assistant", "tool"}
    invalid: list[str] = []
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            invalid.append(f"{index}:<non-object>")
            continue
        role = str(message.get("role") or "").strip().lower()
        if role not in allowed_roles:
            invalid.append(f"{index}:{role or '<missing>'}")
    return invalid


def extract_openai_content(payload: Dict[str, Any]) -> str:
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


def extract_openai_tool_calls(payload: Dict[str, Any]) -> list[dict[str, Any]]:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return []
    first = choices[0]
    if not isinstance(first, dict):
        return []
    message = first.get("message")
    if not isinstance(message, dict):
        return []
    tool_calls = message.get("tool_calls")
    if not isinstance(tool_calls, list):
        return []
    return [item for item in tool_calls if isinstance(item, dict)]


def _to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and float(value).is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


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


def _ns_to_ms(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value) / 1_000_000.0


def extract_openai_usage(payload: Dict[str, Any]) -> tuple[int | None, int | None, int | None]:
    usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
    prompt_tokens = _to_int(usage.get("prompt_tokens"))
    completion_tokens = _to_int(usage.get("completion_tokens"))
    total_tokens = _to_int(usage.get("total_tokens"))
    if total_tokens is None and isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
        total_tokens = prompt_tokens + completion_tokens
    return prompt_tokens, completion_tokens, total_tokens


def extract_openai_timings(payload: Dict[str, Any], latency_ms: int) -> tuple[float, float, float]:
    timings = payload.get("timings") if isinstance(payload.get("timings"), dict) else {}

    prompt_ms = _to_float(timings.get("prompt_ms"))
    predicted_ms = _to_float(timings.get("predicted_ms"))
    total_ms = _to_float(timings.get("total_ms"))

    if prompt_ms is None:
        prompt_ms = _ns_to_ms(timings.get("prompt_eval_duration"))
    if predicted_ms is None:
        predicted_ms = _ns_to_ms(timings.get("eval_duration"))
    if total_ms is None:
        total_ms = _ns_to_ms(timings.get("total_duration"))

    if prompt_ms is None:
        prompt_ms = _ns_to_ms(payload.get("prompt_eval_duration"))
    if predicted_ms is None:
        predicted_ms = _ns_to_ms(payload.get("eval_duration"))
    if total_ms is None:
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


def build_orket_session_id(
    *,
    runtime_context: Mapping[str, Any],
    model: str,
    provider_name: str,
    fallback_messages: List[Dict[str, Any]],
    preferred_session_id: str = "",
) -> str:
    preferred = str(preferred_session_id or "").strip()
    if preferred:
        return preferred
    for key in ("seat_id", "thread_id", "run_id", "session_id"):
        value = str(runtime_context.get(key) or "").strip()
        if value:
            return value
    fallback_payload = {
        "provider_name": provider_name,
        "model": model,
        "messages_head": fallback_messages[:2],
    }
    digest = hashlib.sha256(
        json.dumps(fallback_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    return f"derived-{digest[:16]}"


def build_prompt_fingerprint(payload: Dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def select_response_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    allowed_exact = {
        "content-type",
        "date",
        "server",
        "x-request-id",
        "x-response-id",
        "x-slot-id",
        "openai-processing-ms",
    }
    selected: Dict[str, str] = {}
    for key, value in headers.items():
        lower = str(key).strip().lower()
        if lower in allowed_exact or lower.startswith("x-"):
            selected[lower] = str(value)
    return selected
