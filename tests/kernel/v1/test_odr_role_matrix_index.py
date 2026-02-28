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
        "config": {"rounds": 3},
        "results": [
            {
                "architect_model": "qwen2.5:14b:q8",
                "auditor_model": "gemma3:27b",
                "scenarios": [
                    {
                        "scenario_id": "missing_constraint",
                        "rounds": [{"round": 1}, {"round": 2}],
                        "final_state": {"history_round_count": 2, "stop_reason": "STABLE_DIFF_FLOOR"},
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
    assert run["run_key"] == "qwen2.5:14b:q8__gemma3:27b"
    assert run["is_latest_for_key"] is True
    assert run["runner_round_budget"] == 3 or run["runner_round_budget"] is None
    assert run["provenance_ref"] == "provenance.json::odr_live_role_matrix.test.json"
    scenarios = {row["scenario_id"]: row for row in run["scenarios"]}
    assert scenarios["missing_constraint"]["stop_reason"] == "STABLE_DIFF_FLOOR"
    assert scenarios["missing_constraint"]["rounds_used"] == 2
    assert scenarios["missing_constraint"]["failure_detail"] in {
        "stable_rounds_threshold_reached",
    } or "diff_ratio=" in str(scenarios["missing_constraint"]["failure_detail"])
    assert scenarios["contradiction"]["stop_reason"] == "MAX_SCRIPT_ROUNDS"
    assert scenarios["contradiction"]["rounds_used"] == 1
    assert scenarios["contradiction"]["failure_detail"] == "odr_not_stopped_within_runner_round_budget"


def test_generate_odr_role_matrix_index_includes_code_leak_rule_key(tmp_path: Path) -> None:
    input_dir = tmp_path / "odr"
    input_dir.mkdir(parents=True, exist_ok=True)

    run_payload = {
        "run_v": "1.0.0",
        "generated_at": "2026-02-27T00:00:00+00:00",
        "config": {"rounds": 8},
        "results": [
            {
                "architect_model": "qwen2.5-coder:14b",
                "auditor_model": "deepseek-r1:32b",
                "scenarios": [
                    {
                        "scenario_id": "missing_constraint",
                        "rounds": [
                            {
                                "round": 4,
                                "odr_trace_record": {
                                    "architect_raw": "### REQUIREMENT\nimport policy details\n",
                                    "auditor_raw": "### CRITIQUE\nok\n",
                                    "run_config": {
                                        "code_leak_patterns": [
                                            r"(?s)```.*?```",
                                            r"\b(def|class|import|fn|let|const|interface|type)\b",
                                            r"\b(npm|pip|cargo|docker|venv|node_modules)\b",
                                        ]
                                    },
                                    "metrics": {"code_leak_hit": True},
                                    "stop_reason": "CODE_LEAK",
                                }
                            }
                        ],
                        "final_state": {"history_round_count": 4, "stop_reason": "CODE_LEAK"},
                    }
                ],
            }
        ],
    }
    (input_dir / "odr_live_role_matrix.test_leak.json").write_text(
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
    run = index_payload["runs"][0]
    scenarios = {row["scenario_id"]: row for row in run["scenarios"]}
    assert scenarios["missing_constraint"]["stop_reason"] == "CODE_LEAK"
    assert scenarios["missing_constraint"]["failure_detail"] == "code_leak_rule=source_keyword"
