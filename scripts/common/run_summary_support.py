from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from orket.runtime.run_summary import validate_run_summary_payload


def load_validated_run_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("run_summary_invalid")
    validate_run_summary_payload(payload)
    return payload


def load_validated_run_summary_or_empty(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_validated_run_summary(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def load_first_validated_run_summary(paths: Iterable[Path]) -> dict[str, Any] | None:
    for path in paths:
        payload = load_validated_run_summary_or_empty(path)
        if payload:
            return payload
    return None


__all__ = [
    "load_first_validated_run_summary",
    "load_validated_run_summary",
    "load_validated_run_summary_or_empty",
]
