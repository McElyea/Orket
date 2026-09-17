"""Aggregate complete, versioned model timing observations from retained logs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

from orket.core.contracts.model_timing import MODEL_TIMING_SCHEMA_VERSION, nonnegative_duration
from orket_extension_sdk.llm import nonnegative_int_or_none


def _round3(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _default_token_metrics(total_turn_seconds: float) -> dict[str, Any]:
    return {
        "status": "TOKEN_AND_TIMING_UNAVAILABLE",
        "counts": {"prompt_tokens": None, "output_tokens": None, "total_tokens": None},
        "latencies": {"prefill_seconds": None, "decode_seconds": None,
                      "total_turn_seconds": _round3(float(total_turn_seconds))},
        "throughput": {"prompt_tokens_per_second": None, "generation_tokens_per_second": None},
        "audit": {"raw_usage": {}, "raw_timings": {}},
    }


@dataclass
class _Totals:
    turns: int = 0
    counted: int = 0
    totalled: int = 0
    timed: int = 0
    prompt_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    prompt_ms: float = 0.0
    predicted_ms: float = 0.0

    def include(self, payload: Any) -> None:
        self.turns += 1
        if isinstance(payload, int):
            payload = {"total_tokens": payload}
        if not isinstance(payload, dict):
            return
        prompt = nonnegative_int_or_none(payload.get("prompt_tokens"))
        output = nonnegative_int_or_none(payload.get("output_tokens"))
        total = nonnegative_int_or_none(payload.get("total_tokens"))
        if prompt is not None and output is not None:
            self.counted += 1
            self.prompt_tokens += prompt
            self.output_tokens += output
        if total is not None:
            self.totalled += 1
            self.total_tokens += total
        prompt_ms = nonnegative_duration(payload.get("prompt_ms"))
        predicted_ms = nonnegative_duration(payload.get("predicted_ms"))
        if (payload.get("timing_schema_version") == MODEL_TIMING_SCHEMA_VERSION
                and payload.get("timing_posture") == "reported"
                and prompt_ms is not None and predicted_ms is not None):
            self.timed += 1
            self.prompt_ms += prompt_ms
            self.predicted_ms += predicted_ms

    def metrics(self, total_turn_seconds: float) -> dict[str, Any]:
        metrics = _default_token_metrics(total_turn_seconds)
        if not self.turns:
            return metrics
        has_tokens = self.counted == self.turns
        has_timings = (self.timed == self.turns and nonnegative_duration(self.prompt_ms) is not None
                       and nonnegative_duration(self.predicted_ms) is not None)
        metrics["status"] = ("OK" if has_tokens and has_timings else "TOKEN_COUNT_UNAVAILABLE" if has_timings
                             else "TIMING_UNAVAILABLE" if has_tokens else "TOKEN_AND_TIMING_UNAVAILABLE")
        total = self.total_tokens if self.totalled == self.turns else self.prompt_tokens + self.output_tokens if has_tokens else None
        prefill = _round3(self.prompt_ms / 1000.0) if has_timings else None
        decode = _round3(self.predicted_ms / 1000.0) if has_timings else None
        metrics["counts"] = {"prompt_tokens": self.prompt_tokens if has_tokens else None,
                             "output_tokens": self.output_tokens if has_tokens else None, "total_tokens": total}
        metrics["latencies"].update(prefill_seconds=prefill, decode_seconds=decode)
        if has_tokens and prefill is not None and prefill > 0:
            metrics["throughput"]["prompt_tokens_per_second"] = round(self.prompt_tokens / prefill, 2)
        if has_tokens and decode is not None and decode > 0:
            metrics["throughput"]["generation_tokens_per_second"] = round(self.output_tokens / decode, 2)
        metrics["audit"] = {
            "raw_usage": {"prompt_tokens": self.prompt_tokens if has_tokens else None,
                          "completion_tokens": self.output_tokens if has_tokens else None, "total_tokens": total},
            "raw_timings": {"prompt_ms": _round3(self.prompt_ms) if has_timings else None,
                            "predicted_ms": _round3(self.predicted_ms) if has_timings else None},
        }
        return metrics


def _extract_token_metrics_from_log(*, log_path: Path, session_id: str, total_turn_seconds: float) -> dict[str, Any]:
    totals = _Totals()
    if not log_path.exists() or not session_id:
        return totals.metrics(total_turn_seconds)
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or str(record.get("event") or "").strip() != "turn_complete":
            continue
        data = record.get("data")
        data = data if isinstance(data, dict) else {}
        runtime = data.get("runtime_event")
        runtime = runtime if isinstance(runtime, dict) else {}
        if str(runtime.get("session_id") or data.get("session_id") or "").strip() == session_id:
            totals.include(runtime.get("tokens", data.get("tokens")))
    return totals.metrics(total_turn_seconds)
