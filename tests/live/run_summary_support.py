from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.common.run_summary_support import load_validated_run_summary, require_non_degraded_run_summary


def read_validated_run_summary(path: Path) -> dict[str, Any]:
    payload = require_non_degraded_run_summary(
        load_validated_run_summary(path),
        error_code="live_run_summary_degraded",
    )
    if not isinstance(payload, dict):
        raise ValueError("live_run_summary_invalid")
    return payload
