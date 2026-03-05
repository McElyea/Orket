from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any


def now_utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def tail_text(text: str, *, lines: int = 80) -> str:
    chunk = (text or "").splitlines()
    if len(chunk) <= lines:
        return "\n".join(chunk)
    return "\n".join(chunk[-lines:])


def to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def extract_gate_run_id(text: str) -> str:
    match = re.search(r"GATE_RUN_ID=([A-Za-z0-9_-]+)", text or "")
    if match:
        return match.group(1)
    fallback = re.search(r"gate_run_id=([A-Za-z0-9_-]+)", text or "")
    return fallback.group(1) if fallback else ""
