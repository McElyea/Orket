from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_orchestration_overhead_consistency_passes_with_required_fields(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "test_runs": [
                    {
                        "outcome": "pass",
                        "telemetry": {
                            "internal_model_seconds": 1.2,
                            "orchestration_overhead_ratio": 0.11,
                            "run_quality_reasons": [],
                        },
                    },
                    {
                        "outcome": "fail",
                        "telemetry": {
                            "internal_model_seconds": None,
                            "orchestration_overhead_ratio": None,
                            "run_quality_reasons": ["MISSING_TOKEN_TIMINGS"],
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_orchestration_overhead_consistency.py",
            "--report",
            str(report),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["failures"] == []


def test_check_orchestration_overhead_consistency_fails_on_missing_fields(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "test_runs": [
                    {
                        "outcome": "pass",
                        "telemetry": {
                            "internal_model_seconds": 1.2,
                        },
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "check.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_orchestration_overhead_consistency.py",
            "--report",
            str(report),
            "--out",
            str(out),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert any("missing:orchestration_overhead_ratio" in item for item in payload["failures"])
    assert any("missing:run_quality_reasons" in item for item in payload["failures"])

