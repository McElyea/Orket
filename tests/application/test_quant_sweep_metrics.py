from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

METRICS_PATH = SCRIPTS_ROOT / "quant_sweep" / "metrics.py"
SPEC = importlib.util.spec_from_file_location("quant_sweep_metrics_module", METRICS_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load metrics module from {METRICS_PATH}")
METRICS_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(METRICS_MODULE)
collect_quant_metrics = METRICS_MODULE.collect_quant_metrics


def _report(
    *,
    token_statuses: list[str],
    overheads: list[float],
    reason_rows: list[list[str]] | None = None,
) -> dict:
    runs = []
    for idx, status in enumerate(token_statuses):
        overhead = overheads[idx] if idx < len(overheads) else overheads[-1]
        run_quality_reasons = []
        run_quality_status = "CLEAN"
        if status != "OK":
            run_quality_reasons.append("MISSING_TOKEN_TIMINGS")
            run_quality_status = "POLLUTED"
        if overhead > 0.25:
            run_quality_reasons.append("HIGH_ORCHESTRATION_OVERHEAD")
            run_quality_status = "POLLUTED"
        if reason_rows and idx < len(reason_rows):
            for reason in reason_rows[idx]:
                normalized = str(reason).strip().upper()
                if normalized:
                    run_quality_reasons.append(normalized)
            if run_quality_reasons:
                run_quality_status = "POLLUTED"
        runs.append(
            {
                "telemetry": {
                    "adherence_score": 1.0,
                    "peak_memory_rss": 100.0,
                    "total_latency": 3.0,
                    "init_latency": None,
                    "orchestration_overhead_ratio": overhead,
                    "run_quality_status": run_quality_status,
                    "run_quality_reasons": run_quality_reasons,
                    "token_metrics_status": status,
                    "token_metrics": {
                        "status": status,
                        "throughput": {
                            "prompt_tokens_per_second": None,
                            "generation_tokens_per_second": 100.0,
                        },
                    },
                }
            }
        )
    return {"test_runs": runs, "determinism_rate": 0.0}


def test_collect_quant_metrics_strict_defaults_keep_polluted_row() -> None:
    report = _report(token_statuses=["OK", "TOKEN_AND_TIMING_UNAVAILABLE"], overheads=[0.55, 0.55])
    metrics = collect_quant_metrics(report)
    assert metrics["token_metrics_status"] == "TOKEN_AND_TIMING_UNAVAILABLE"
    assert metrics["run_quality_status"] == "POLLUTED"
    assert "MISSING_TOKEN_TIMINGS" in metrics["run_quality_reasons"]
    assert "HIGH_ORCHESTRATION_OVERHEAD" in metrics["run_quality_reasons"]


def test_collect_quant_metrics_tolerant_policy_can_clear_row() -> None:
    report = _report(token_statuses=["OK", "TOKEN_AND_TIMING_UNAVAILABLE"], overheads=[0.55, 0.55])
    metrics = collect_quant_metrics(
        report,
        max_missing_telemetry_rate=0.6,
        max_orchestration_overhead_ratio=0.65,
    )
    assert metrics["missing_telemetry_rate"] == 0.5
    assert metrics["token_metrics_status"] == "OK"
    assert metrics["run_quality_status"] == "CLEAN"
    assert metrics["run_quality_reasons"] == []


def test_collect_quant_metrics_cpu_saturation_tolerance() -> None:
    report = _report(
        token_statuses=["OK", "OK", "OK"],
        overheads=[0.55, 0.55, 0.55],
        reason_rows=[["HIGH_CPU_SATURATION"], [], []],
    )
    strict = collect_quant_metrics(
        report,
        max_missing_telemetry_rate=0.6,
        max_orchestration_overhead_ratio=0.65,
    )
    tolerant = collect_quant_metrics(
        report,
        max_missing_telemetry_rate=0.6,
        max_orchestration_overhead_ratio=0.65,
        max_cpu_saturation_rate=0.5,
    )
    assert strict["run_quality_status"] == "POLLUTED"
    assert "HIGH_CPU_SATURATION" in strict["run_quality_reasons"]
    assert tolerant["run_quality_status"] == "CLEAN"
    assert tolerant["run_quality_reasons"] == []
