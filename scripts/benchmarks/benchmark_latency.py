"""Reported run-duration coverage shared by scoring and human projections."""
from __future__ import annotations

from statistics import mean
from typing import Any

from orket.core.contracts.model_timing import nonnegative_duration

LATENCY_SCHEMA = "benchmark_latency.v1"
LATENCY_SOURCE = "input_run.duration_ms"


def _status(samples: int, total: int) -> str:
    return "unavailable" if samples == 0 else "reported" if samples == total else "partial"


def summarize_latency(values: list[Any]) -> dict[str, Any]:
    samples = [duration for value in values if (duration := nonnegative_duration(value)) is not None]
    status = _status(len(samples), len(values))
    return {
        "avg_latency_ms": round(mean(samples), 3) if status == "reported" else None,
        "latency_summary": {
            "schema_version": LATENCY_SCHEMA, "status": status, "source": LATENCY_SOURCE,
            "samples_reported": len(samples), "runs_total": len(values),
        },
    }


def read_latency_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("schema_version") != "v2":
        return {
            "avg_latency_ms": None, "legacy_avg_latency_ms": nonnegative_duration(payload.get("avg_latency_ms")),
            "latency_summary": {"schema_version": LATENCY_SCHEMA, "status": "legacy_unverified",
                                "source": "legacy_scored_report", "samples_reported": None, "runs_total": None},
        }
    summary = payload.get("latency_summary")
    if not isinstance(summary, dict):
        raise ValueError("E_BENCHMARK_LATENCY_SUMMARY_INVALID")
    samples, total = summary.get("samples_reported"), summary.get("runs_total")
    if (type(samples) is not int or type(total) is not int or not 0 <= samples <= total
            or summary.get("schema_version") != LATENCY_SCHEMA or summary.get("source") != LATENCY_SOURCE
            or summary.get("status") != _status(samples, total)):
        raise ValueError("E_BENCHMARK_LATENCY_SUMMARY_INVALID")
    value = nonnegative_duration(payload.get("avg_latency_ms"))
    if ((summary["status"] == "reported" and value is None)
            or (summary["status"] != "reported" and payload.get("avg_latency_ms") is not None)):
        raise ValueError("E_BENCHMARK_LATENCY_SUMMARY_INVALID")
    return {"avg_latency_ms": value, "latency_summary": dict(summary)}
