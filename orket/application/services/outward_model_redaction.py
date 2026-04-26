from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import Any

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{8,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{8,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9\-]{8,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]{12,}"),
)


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        redacted = value
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub("[REDACTED]", redacted)
        return redacted
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, Mapping):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value


def redact_prompt_messages(messages: list[dict[str, str]], pii_fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        {str(key): (_redact_prompt_content(value, pii_fields) if key == "content" else redact_value(value)) for key, value in item.items()}
        for item in messages
    ]


def _redact_prompt_content(value: Any, pii_fields: tuple[str, ...]) -> Any:
    if not isinstance(value, str):
        return redact_value(value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return redact_value(value)
    return json.dumps(_redact_prompt_payload(parsed, pii_fields), sort_keys=True, indent=2)


def _redact_prompt_payload(value: Any, pii_fields: tuple[str, ...]) -> Any:
    if isinstance(value, list):
        return [_redact_prompt_payload(item, pii_fields) for item in value]
    if isinstance(value, Mapping):
        protected = {"content", *pii_fields}
        return {
            str(key): "[REDACTED]" if str(key) in protected else _redact_prompt_payload(item, pii_fields)
            for key, item in value.items()
        }
    return redact_value(value)


__all__ = ["redact_prompt_messages", "redact_value"]
