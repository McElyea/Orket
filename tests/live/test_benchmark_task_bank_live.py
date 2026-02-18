from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(
    os.getenv("ORKET_RUN_BENCHMARK_LIVE_100", "").strip().lower() not in {"1", "true", "yes"},
    reason="Set ORKET_RUN_BENCHMARK_LIVE_100=1 to execute 001-100 live card benchmark run.",
)
def test_benchmark_task_bank_runs_live_through_card_system() -> None:
    raw_out = Path("benchmarks/results/live_card_100_determinism_report.json")
    scored_out = Path("benchmarks/results/live_card_100_scored_report.json")
    result = subprocess.run(
        [
            "python",
            "scripts/run_live_card_benchmark_suite.py",
            "--runs",
            "1",
            "--raw-out",
            str(raw_out),
            "--scored-out",
            str(scored_out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    raw = json.loads(raw_out.read_text(encoding="utf-8"))
    scored = json.loads(scored_out.read_text(encoding="utf-8"))

    assert raw["total_tasks"] == 100
    assert raw["task_id_min"] == 1
    assert raw["task_id_max"] == 100
    assert scored["input_report"] == "benchmarks/task_bank/v1/tasks.json"
