from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_quant_sweep_kpis_passes_when_thresholds_met(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "stability_kpis": {
                    "determinism_rate": 1.0,
                    "missing_telemetry_rate": 0.0,
                    "polluted_run_rate": 0.0,
                    "frontier_success_rate": 1.0,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_quant_sweep_kpis.py", "--summary", str(summary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_check_quant_sweep_kpis_fails_when_thresholds_breached(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "stability_kpis": {
                    "determinism_rate": 0.8,
                    "missing_telemetry_rate": 0.2,
                    "polluted_run_rate": 0.3,
                    "frontier_success_rate": 0.4,
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_quant_sweep_kpis.py", "--summary", str(summary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert len(payload["failures"]) >= 1
