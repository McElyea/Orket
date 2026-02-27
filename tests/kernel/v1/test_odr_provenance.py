from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_generate_odr_provenance_no_probes(tmp_path: Path) -> None:
    input_dir = tmp_path / "odr"
    input_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "run_v": "1.0.0",
        "generated_at": "2026-02-27T01:00:00+00:00",
        "config": {"rounds": 3, "temperature": 0.1, "timeout": 180},
        "results": [
            {
                "architect_model": "qwen2.5:14b",
                "auditor_model": "deepseek-r1:32b",
                "started_at": "2026-02-27T01:00:01+00:00",
                "ended_at": "2026-02-27T01:00:11+00:00",
                "scenarios": [],
            }
        ],
    }
    (input_dir / "odr_live_role_matrix.test.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    out = input_dir / "provenance.json"
    cmd = [
        sys.executable,
        "scripts/generate_odr_provenance.py",
        "--input-dir",
        str(input_dir),
        "--out",
        str(out),
        "--no-probes",
    ]
    subprocess.run(cmd, check=True)

    prov = json.loads(out.read_text(encoding="utf-8"))
    assert prov["prov_v"] == "1.0.0"
    assert prov["run_count"] == 1
    row = prov["runs"][0]
    assert row["file"] == "odr_live_role_matrix.test.json"
    assert row["duration_ms"] == 10000
    assert row["runner_round_budget"] == 3
    assert row["runtime"]["ollama_version"] is None
    assert row["runtime"]["orket_git_commit"] is None
