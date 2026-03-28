from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common.run_summary_support import load_validated_run_summary


def read_validated_run_summary(path: Path) -> dict[str, Any]:
    payload = load_validated_run_summary(path)
    if not isinstance(payload, dict):
        raise ValueError("live_run_summary_invalid")
    return payload
