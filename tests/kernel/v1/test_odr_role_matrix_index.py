from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_generate_odr_role_matrix_index(tmp_path: Path) -> None:
    input_dir = tmp_path / "odr"
    input_dir.mkdir(parents=True, exist_ok=True)

    run_payload = {
        "run_v": "1.0.0",
        "generated_at": "2026-02-27T00:00:00+00:00",
        "results": [
            {
                "architect_model": "qwen2.5:14b:q8",
                "auditor_model": "gemma3:27b",
                "scenarios": [
                    {
                        "scenario_id": "missing_constraint",
                        "rounds": [{"round": 1}, {"round": 2}],
                        "final_state": {"history_round_count": 2, "stop_reason": "DIFF_FLOOR"},
                    },
                    {
                        "scenario_id": "contradiction",
                        "rounds": [{"round": 1}],
                        "final_state": {"history_round_count": 1, "stop_reason": None},
                    },
                ],
            }
        ],
    }
    (input_dir / "odr_live_role_matrix.test.json").write_text(
        json.dumps(run_payload, indent=2) + "\n",
        encoding="utf-8",
    )

    out_path = input_dir / "index.json"
    cmd = [
        sys.executable,
        "scripts/generate_odr_role_matrix_index.py",
        "--input-dir",
        str(input_dir),
        "--out",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)

    index_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert index_payload["index_v"] == "1.0.0"
    assert index_payload["run_count"] == 1
    run = index_payload["runs"][0]
    assert run["architect_model"] == "qwen2.5:14b:q8"
    assert run["auditor_model"] == "gemma3:27b"
    scenarios = {row["scenario_id"]: row for row in run["scenarios"]}
    assert scenarios["missing_constraint"]["stop_reason"] == "DIFF_FLOOR"
    assert scenarios["missing_constraint"]["rounds_used"] == 2
    assert scenarios["contradiction"]["stop_reason"] is None
    assert scenarios["contradiction"]["rounds_used"] == 1
