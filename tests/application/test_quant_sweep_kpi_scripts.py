from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_quant_sweep_kpis_fails_on_polluted_rate(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "1.1.3",
                "stability_kpis": {
                    "determinism_rate": 1.0,
                    "missing_telemetry_rate": 0.0,
                    "polluted_run_rate": 1.0,
                    "frontier_success_rate": 0.0,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_quant_sweep_kpis.py",
            "--summary",
            str(summary),
            "--max-polluted-run-rate",
            "0.10",
            "--min-frontier-success-rate",
            "0.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
    assert any("polluted_run_rate" in item for item in payload["failures"])


def test_quant_sweep_kpi_report_extracts_stability_block(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    out = tmp_path / "sweep_kpis.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "1.1.3",
                "stability_kpis": {
                    "determinism_rate": 1.0,
                    "missing_telemetry_rate": 0.0,
                    "polluted_run_rate": 0.0,
                    "frontier_success_rate": 1.0,
                    "quant_rows": 3,
                    "sessions": 1,
                    "weighted_runs": 3,
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/quant_sweep_kpi_report.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["stability_kpis"]["frontier_success_rate"] == 1.0
    assert payload["stability_kpis"]["weighted_runs"] == 3
