from __future__ import annotations

import json
import re
from typing import Any

_PATTERN_SPECS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("PEM_PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", re.IGNORECASE)),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN_CLASSIC", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    ("GITHUB_TOKEN_FINE_GRAINED", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    (
        "ENV_SECRET_ASSIGNMENT",
        re.compile(
            r"(?im)^\s*(?:AWS_SECRET_ACCESS_KEY|OPENAI_API_KEY|GITHUB_TOKEN|SLACK_BOT_TOKEN|AZURE_OPENAI_API_KEY)\s*=\s*[^\s]+"
        ),
    ),
    ("US_SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
)


def _to_scan_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(value)


def find_leak_hits(value: Any) -> list[str]:
    text = _to_scan_text(value)
    if not text:
        return []
    hits: list[str] = []
    for code, pattern in _PATTERN_SPECS:
        if pattern.search(text) and code not in hits:
            hits.append(code)
    return sorted(hits)


def has_leak_hits(value: Any) -> bool:
    return bool(find_leak_hits(value))


def sanitize_text(value: str) -> str:
    sanitized = str(value)
    for code, pattern in _PATTERN_SPECS:
        _ = code
        sanitized = pattern.sub("[REDACTED]", sanitized)
    return sanitized


__all__ = ["find_leak_hits", "has_leak_hits", "sanitize_text"]
