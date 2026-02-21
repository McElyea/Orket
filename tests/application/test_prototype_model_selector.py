from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_prototype_model_selector_picks_best_valid_candidate(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "model_id": "model-a",
                        "per_quant": [
                            {"quant_tag": "Q8_0", "valid": True, "adherence_score": 0.98, "total_latency": 2.0},
                            {"quant_tag": "Q6_K", "valid": True, "adherence_score": 0.96, "total_latency": 1.5},
                            {"quant_tag": "Q4_K_M", "valid": False, "adherence_score": 1.0, "total_latency": 0.5},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "selector.json"
    result = subprocess.run(
        [
            "python",
            "scripts/prototype_model_selector.py",
            "--summary",
            str(summary),
            "--out",
            str(out),
            "--min-adherence",
            "0.95",
            "--max-latency",
            "10.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "selector.prototype.v1"
    assert payload["candidate_count"] == 2
    assert payload["selected"]["quant_tag"] == "Q6_K"


def test_prototype_model_selector_returns_none_when_no_candidate_qualifies(tmp_path: Path) -> None:
    summary = tmp_path / "summary.json"
    summary.write_text(
        json.dumps(
            {
                "sessions": [
                    {
                        "model_id": "model-a",
                        "per_quant": [
                            {"quant_tag": "Q8_0", "valid": False, "adherence_score": 0.99, "total_latency": 1.0},
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "selector.json"
    result = subprocess.run(
        [
            "python",
            "scripts/prototype_model_selector.py",
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
    assert payload["candidate_count"] == 0
    assert payload["selected"] is None

