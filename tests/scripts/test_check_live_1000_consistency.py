from __future__ import annotations

import json
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/check_live_1000_consistency.py")


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python", str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def _base_report() -> dict:
    metric_template = {
        "samples": 100,
        "failures": 0,
        "p50_ms": 100.0,
        "p95_ms": 150.0,
        "p99_ms": 175.0,
        "error_rate_percent": 0.0,
    }
    metrics_one = {
        "webhook": dict(metric_template),
        "api_heartbeat": dict(metric_template),
        "parallel_epic_trigger": dict(metric_template),
        "websocket_connect": dict(metric_template),
    }
    metrics_two = {
        "webhook": {**metric_template, "p50_ms": 105.0, "p95_ms": 156.0, "p99_ms": 178.0},
        "api_heartbeat": {**metric_template, "p50_ms": 96.0, "p95_ms": 148.0, "p99_ms": 172.0},
        "parallel_epic_trigger": {**metric_template, "p50_ms": 103.0, "p95_ms": 153.0, "p99_ms": 176.0},
        "websocket_connect": {**metric_template, "p50_ms": 110.0, "p95_ms": 165.0, "p99_ms": 185.0},
    }
    return {
        "schema_version": "live_1000_consistency_v1",
        "generated_at_utc": "2026-03-04T00:00:00+00:00",
        "config": {
            "stream_loops": 2,
            "stress_runs": 2,
        },
        "stream_gate": {
            "enabled": True,
            "ok": True,
            "return_code": 0,
            "summary": {
                "scenarios": [
                    {
                        "scenario_id": "s7_real_model_happy_path",
                        "runs": 2,
                        "status_counts": {"PASS": 2},
                        "law_checker_failures": 0,
                        "terminal_event_values": ["turn_final"],
                        "commit_outcome_values": ["ok"],
                        "min_expected_token_deltas": 1,
                        "token_delta_min": 1,
                    },
                    {
                        "scenario_id": "s8_real_model_cancel_mid_gen",
                        "runs": 2,
                        "status_counts": {"PASS": 2},
                        "law_checker_failures": 0,
                        "terminal_event_values": ["turn_interrupted"],
                        "commit_outcome_values": [""],
                        "min_expected_token_deltas": 0,
                        "token_delta_min": 0,
                    },
                ]
            },
        },
        "stress": {
            "enabled": True,
            "ok": True,
            "runs_requested": 2,
            "runs_completed": 2,
            "run_summaries": [
                {"index": 1, "return_code": 0, "metrics": metrics_one},
                {"index": 2, "return_code": 0, "metrics": metrics_two},
            ],
        },
        "ok": True,
    }


def test_check_live_1000_consistency_passes_with_valid_report(tmp_path: Path) -> None:
    report_path = tmp_path / "live_report.json"
    report_path.write_text(json.dumps(_base_report(), indent=2), encoding="utf-8")

    result = _run(
        "--report",
        str(report_path),
        "--expected-stream-loops",
        "2",
        "--expected-stress-runs",
        "2",
        "--max-p50-drift-pct",
        "20",
        "--max-p95-drift-pct",
        "20",
        "--max-p99-drift-pct",
        "20",
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["issues"] == []


def test_check_live_1000_consistency_fails_on_stress_failure(tmp_path: Path) -> None:
    report = _base_report()
    report["stress"]["run_summaries"][1]["metrics"]["websocket_connect"]["failures"] = 1
    report["ok"] = False
    report_path = tmp_path / "live_report_fail.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    result = _run(
        "--report",
        str(report_path),
        "--expected-stream-loops",
        "2",
        "--expected-stress-runs",
        "2",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ok"] is False
    assert any("stress:run_0002:websocket_connect:failures=1" in issue for issue in payload["issues"])
