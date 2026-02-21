from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_quant_sweep_kpi_report_extracts_block(tmp_path: Path) -> None:
    summary = tmp_path / "sweep_summary.json"
    summary.write_text(
        json.dumps(
            {
                "schema_version": "1.1.3",
                "stability_kpis": {
                    "determinism_rate": 1.0,
                    "missing_telemetry_rate": 0.0,
                    "polluted_run_rate": 0.1,
                    "frontier_success_rate": 0.5,
                    "quant_rows": 4,
                    "sessions": 2,
                    "weighted_runs": 8,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    out = tmp_path / "kpis.json"
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
    assert payload["stability_kpis"]["determinism_rate"] == 1.0
    assert payload["stability_kpis"]["polluted_run_rate"] == 0.1
