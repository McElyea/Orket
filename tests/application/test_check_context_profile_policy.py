from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_check_context_profile_policy_passes_for_valid_inputs(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "profiles": {
                    "safe": {"contexts": [1, 2], "adherence_min": 0.95, "ttft_ceiling_ms": 250, "decode_floor_tps": 20},
                    "balanced": {"contexts": [2, 3], "adherence_min": 0.93, "ttft_ceiling_ms": 350, "decode_floor_tps": 15},
                    "stress": {"contexts": [3, 4], "adherence_min": 0.9, "ttft_ceiling_ms": 500, "decode_floor_tps": 10},
                }
            }
        ),
        encoding="utf-8",
    )
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps({"context_sweep_profile": "safe", "context_sweep_contexts": [1, 2]}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_profile_policy.py",
            "--profiles",
            str(profiles),
            "--matrix-configs",
            str(matrix),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_check_context_profile_policy_fails_for_bad_order(tmp_path: Path) -> None:
    profiles = tmp_path / "profiles.json"
    profiles.write_text(
        json.dumps(
            {
                "profiles": {
                    "safe": {"contexts": [1, 2], "adherence_min": 0.90, "ttft_ceiling_ms": 500, "decode_floor_tps": 10},
                    "balanced": {"contexts": [2, 3], "adherence_min": 0.93, "ttft_ceiling_ms": 350, "decode_floor_tps": 15},
                    "stress": {"contexts": [3, 4], "adherence_min": 0.95, "ttft_ceiling_ms": 250, "decode_floor_tps": 20},
                }
            }
        ),
        encoding="utf-8",
    )
    matrix = tmp_path / "matrix.json"
    matrix.write_text(
        json.dumps({"context_sweep_profile": "unknown", "context_sweep_contexts": []}),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/check_context_profile_policy.py",
            "--profiles",
            str(profiles),
            "--matrix-configs",
            str(matrix),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["status"] == "FAIL"
