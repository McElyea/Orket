from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_valid_run_policy_passes_when_frontier_quant_is_valid(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "per_quant": [
                            {"quant_tag": "Q8_0", "valid": True},
                            {"quant_tag": "Q6_K", "valid": False},
                        ],
                        "efficiency_frontier": {"minimum_viable_quant_tag": "Q8_0"},
                        "recommendation_detail": {"minimum_viable_quant": "Q8_0"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        ["python", "scripts/check_valid_run_policy.py", "--summary", str(summary)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_check_valid_run_policy_fails_when_frontier_quant_is_invalid(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "per_quant": [
                            {"quant_tag": "Q8_0", "valid": False},
                        ],
                        "efficiency_frontier": {"minimum_viable_quant_tag": "Q8_0"},
                        "recommendation_detail": {"minimum_viable_quant": "Q8_0"},
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
            "scripts/check_valid_run_policy.py",
            "--summary",
            str(summary),
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
    assert any("frontier_quant_not_valid:Q8_0" in item for item in payload["failures"])
    assert any("recommendation_quant_not_valid:Q8_0" in item for item in payload["failures"])

