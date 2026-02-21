from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_telemetry_artifact_fields_passes_with_required_keys(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "test_runs": [
                    {
                        "outcome": "pass",
                        "telemetry": {
                            "execution_lane": "ci",
                            "vram_profile": "safe",
                            "token_metrics_status": "OK",
                            "token_metrics": {},
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_telemetry_artifact_fields.py",
            "--report",
            str(report),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_check_telemetry_artifact_fields_fails_on_missing_or_invalid(tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "test_runs": [
                    {
                        "outcome": "fail",
                        "telemetry": {
                            "execution_lane": "ci",
                            "token_metrics_status": "NOT_CANONICAL",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "out.json"
    result = subprocess.run(
        [
            "python",
            "scripts/check_telemetry_artifact_fields.py",
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
    assert any("missing:vram_profile" in item for item in payload["failures"])
    assert any("missing:token_metrics" in item for item in payload["failures"])
    assert any("invalid:token_metrics_status:NOT_CANONICAL" in item for item in payload["failures"])

