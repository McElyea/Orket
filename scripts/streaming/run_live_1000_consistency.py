from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from common.rerun_diff_ledger import write_payload_with_diff_ledger

try:
    from scripts.streaming.live_consistency_common import extract_gate_run_id, now_utc_iso, tail_text, to_float, to_int
    from scripts.streaming.live_1000_stream_summary import collect_stream_verdict_summary
except ModuleNotFoundError:  # pragma: no cover - direct script execution fallback
    from live_consistency_common import extract_gate_run_id, now_utc_iso, tail_text, to_float, to_int
    from live_1000_stream_summary import collect_stream_verdict_summary

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run live consistency loops for model-streaming gate and real-service stress."
    )
    parser.add_argument(
        "--out",
        type=str,
        default="benchmarks/results/streaming/live_1000_consistency.json",
        help="Output report path.",
    )
    parser.add_argument(
        "--stream-loops",
        type=int,
        default=1000,
        help="Stability loops for scripts/streaming/run_model_streaming_gate.py (0 disables stream gate).",
    )
    parser.add_argument(
        "--stream-provider-mode",
        choices=["stub", "real"],
        default="real",
        help="Provider mode for stream gate.",
    )
    parser.add_argument(
        "--stream-real-provider",
        choices=["ollama", "openai_compat", "lmstudio"],
        default="lmstudio",
        help="Real provider backend when stream provider mode is real.",
    )
    parser.add_argument(
        "--stream-model-id",
        type=str,
        default="",
        help="Optional ORKET_MODEL_STREAM_REAL_MODEL_ID override.",
    )
    parser.add_argument(
        "--stream-timeout",
        type=float,
        default=30.0,
        help="Per-scenario timeout for stream gate script.",
    )
    parser.add_argument(
        "--stream-scenarios-root",
        type=str,
        default="docs/observability/stream_scenarios",
        help="Scenario directory for stream gate script.",
    )
    parser.add_argument(
        "--stream-skip-preflight",
        action="store_true",
        help="Pass --skip-preflight to stream gate script.",
    )
    parser.add_argument(
        "--stream-preflight-smoke-stream",
        action="store_true",
        help="Pass --preflight-smoke-stream to stream gate script.",
    )
    parser.add_argument(
        "--stream-openai-use-stream",
        action="store_true",
        default=True,
        help="Set ORKET_MODEL_STREAM_OPENAI_USE_STREAM=true for the stream gate run.",
    )
    parser.add_argument(
        "--stream-openai-disable-stream",
        action="store_true",
        help="Set ORKET_MODEL_STREAM_OPENAI_USE_STREAM=false for the stream gate run.",
    )
    parser.add_argument(
        "--stress-runs",
        type=int,
        default=1000,
        help="Loop count for scripts/streaming/real_service_stress.py (0 disables stress suite).",
    )
    parser.add_argument(
        "--stress-profile",
        choices=["baseline", "heavy", "aggressive"],
        default="baseline",
        help="Profile for real-service stress loops.",
    )
    parser.add_argument("--stress-api-port", type=int, default=8082)
    parser.add_argument("--stress-webhook-port", type=int, default=8080)
    parser.add_argument("--stress-health-timeout-sec", type=int, default=90)
    parser.add_argument("--stress-api-key", type=str, default="stress-api-key")
    parser.add_argument("--stress-webhook-test-token", type=str, default="stress-webhook-token")
    parser.add_argument(
        "--stress-out-dir",
        type=str,
        default="benchmarks/results/streaming/live_1000_consistency_stress_runs",
        help="Directory for per-run stress JSON artifacts.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        default=True,
        help="Stop stress loops on first nonzero return code.",
    )
    parser.add_argument(
        "--no-fail-fast",
        action="store_true",
        help="Continue stress loops after failures.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=10,
        help="Print stress progress every N runs.",
    )
    parser.add_argument(
        "--diff-ledger-max",
        type=int,
        default=30,
        help="Maximum number of diff ledger entries retained on --out.",
    )
    return parser.parse_args()


def _run_stream_gate(args: argparse.Namespace) -> dict[str, Any]:
    loops = max(0, int(args.stream_loops))
    if loops <= 0:
        return {"enabled": False, "ok": True}

    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "streaming" / "run_model_streaming_gate.py"),
        "--provider-mode",
        str(args.stream_provider_mode),
        "--scenarios-root",
        str(args.stream_scenarios_root),
        "--timeout",
        str(float(args.stream_timeout)),
        "--stability-loops",
        str(loops),
    ]
    if str(args.stream_provider_mode) == "real":
        cmd.extend(["--real-provider", str(args.stream_real_provider)])
    if bool(args.stream_skip_preflight):
        cmd.append("--skip-preflight")
    if bool(args.stream_preflight_smoke_stream):
        cmd.append("--preflight-smoke-stream")

    env = dict(os.environ)
    env["ORKET_MODEL_STREAM_PROVIDER"] = str(args.stream_provider_mode)
    if str(args.stream_provider_mode) == "real":
        env["ORKET_MODEL_STREAM_REAL_PROVIDER"] = str(args.stream_real_provider)
        if str(args.stream_model_id or "").strip():
            env["ORKET_MODEL_STREAM_REAL_MODEL_ID"] = str(args.stream_model_id).strip()
    use_stream = bool(args.stream_openai_use_stream) and not bool(args.stream_openai_disable_stream)
    env["ORKET_MODEL_STREAM_OPENAI_USE_STREAM"] = "true" if use_stream else "false"

    started = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
    combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    gate_run_id = extract_gate_run_id(combined_output)
    summary = collect_stream_verdict_summary(project_root=PROJECT_ROOT, gate_run_id=gate_run_id, loops_requested=loops)
    return {
        "enabled": True,
        "ok": int(proc.returncode) == 0,
        "return_code": int(proc.returncode),
        "duration_ms": duration_ms,
        "command": cmd,
        "gate_run_id": gate_run_id,
        "summary": summary,
        "stdout_tail": tail_text(proc.stdout or ""),
        "stderr_tail": tail_text(proc.stderr or ""),
    }

def _run_stress_suite(args: argparse.Namespace) -> dict[str, Any]:
    runs_requested = max(0, int(args.stress_runs))
    if runs_requested <= 0:
        return {"enabled": False, "ok": True}

    fail_fast = bool(args.fail_fast) and not bool(args.no_fail_fast)
    stress_root = Path(str(args.stress_out_dir)).resolve()
    run_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    run_dir = stress_root / f"run-{run_stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    run_summaries: list[dict[str, Any]] = []
    for index in range(1, runs_requested + 1):
        out_path = run_dir / f"stress_{index:04d}.json"
        cmd = [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "streaming" / "real_service_stress.py"),
            "--profile",
            str(args.stress_profile),
            "--api-port",
            str(int(args.stress_api_port)),
            "--webhook-port",
            str(int(args.stress_webhook_port)),
            "--health-timeout-sec",
            str(int(args.stress_health_timeout_sec)),
            "--api-key",
            str(args.stress_api_key),
            "--webhook-test-token",
            str(args.stress_webhook_test_token),
            "--out",
            str(out_path),
        ]
        started = time.perf_counter()
        proc = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        duration_ms = round((time.perf_counter() - started) * 1000.0, 3)
        payload = {}
        if out_path.exists():
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        metrics = payload.get("results") if isinstance(payload.get("results"), dict) else {}
        run_summary = {
            "index": index,
            "return_code": int(proc.returncode),
            "duration_ms": duration_ms,
            "report_path": str(out_path),
            "metrics": metrics,
            "stdout_tail": tail_text(proc.stdout or "", lines=30),
            "stderr_tail": tail_text(proc.stderr or "", lines=30),
        }
        run_summaries.append(run_summary)

        if index == 1 or index % max(1, int(args.progress_every)) == 0 or proc.returncode != 0:
            print(
                f"[live-1000] stress run {index}/{runs_requested} rc={proc.returncode} "
                f"duration_ms={duration_ms:.1f}"
            )
        if proc.returncode != 0 and fail_fast:
            break

    metric_names: set[str] = set()
    for run in run_summaries:
        metric_names.update((run.get("metrics") or {}).keys())

    aggregate_metrics: dict[str, Any] = {}
    for metric_name in sorted(metric_names):
        rows = [run.get("metrics", {}).get(metric_name, {}) for run in run_summaries if isinstance(run.get("metrics"), dict)]
        p50_values = [to_float(row.get("p50_ms"), default=0.0) for row in rows if row.get("p50_ms") is not None]
        p95_values = [to_float(row.get("p95_ms"), default=0.0) for row in rows if row.get("p95_ms") is not None]
        p99_values = [to_float(row.get("p99_ms"), default=0.0) for row in rows if row.get("p99_ms") is not None]
        error_rates = [to_float(row.get("error_rate_percent"), default=0.0) for row in rows]
        failures = [to_int(row.get("failures"), default=0) for row in rows]

        def _range(values: list[float]) -> dict[str, float | None]:
            if not values:
                return {"min": None, "median": None, "max": None}
            return {
                "min": round(min(values), 3),
                "median": round(statistics.median(values), 3),
                "max": round(max(values), 3),
            }

        aggregate_metrics[metric_name] = {
            "runs_with_metric": len(rows),
            "failures_total": sum(failures),
            "error_rate_percent_max": round(max(error_rates), 4) if error_rates else None,
            "p50_ms": _range(p50_values),
            "p95_ms": _range(p95_values),
            "p99_ms": _range(p99_values),
        }

    ok = True
    if not run_summaries:
        ok = False
    for run in run_summaries:
        if to_int(run.get("return_code"), default=1) != 0:
            ok = False
            break
        metrics = run.get("metrics") if isinstance(run.get("metrics"), dict) else {}
        for payload in metrics.values():
            if to_int(payload.get("failures"), default=0) > 0:
                ok = False
                break
        if not ok:
            break

    return {
        "enabled": True,
        "ok": ok,
        "runs_requested": runs_requested,
        "runs_completed": len(run_summaries),
        "fail_fast": fail_fast,
        "run_dir": str(run_dir),
        "run_summaries": run_summaries,
        "aggregate_metrics": aggregate_metrics,
    }

def main() -> int:
    args = _parse_args()
    stream_result = _run_stream_gate(args)
    stress_result = _run_stress_suite(args)

    report = {
        "schema_version": "live_1000_consistency_v1",
        "generated_at_utc": now_utc_iso(),
        "config": {
            "stream_loops": int(args.stream_loops),
            "stream_provider_mode": str(args.stream_provider_mode),
            "stream_real_provider": str(args.stream_real_provider),
            "stream_model_id": str(args.stream_model_id or ""),
            "stream_timeout": float(args.stream_timeout),
            "stream_scenarios_root": str(args.stream_scenarios_root),
            "stream_skip_preflight": bool(args.stream_skip_preflight),
            "stream_preflight_smoke_stream": bool(args.stream_preflight_smoke_stream),
            "stream_openai_use_stream": bool(args.stream_openai_use_stream) and not bool(args.stream_openai_disable_stream),
            "stress_runs": int(args.stress_runs),
            "stress_profile": str(args.stress_profile),
            "stress_api_port": int(args.stress_api_port),
            "stress_webhook_port": int(args.stress_webhook_port),
            "stress_health_timeout_sec": int(args.stress_health_timeout_sec),
            "stress_out_dir": str(args.stress_out_dir),
            "fail_fast": bool(args.fail_fast) and not bool(args.no_fail_fast),
        },
        "stream_gate": stream_result,
        "stress": stress_result,
        "ok": bool(stream_result.get("ok", True)) and bool(stress_result.get("ok", True)),
    }

    out_path = Path(str(args.out)).resolve()
    persisted = write_payload_with_diff_ledger(
        out_path,
        report,
        max_entries=max(1, int(args.diff_ledger_max)),
    )
    print(json.dumps(persisted, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
