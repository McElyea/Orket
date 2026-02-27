from __future__ import annotations

import json
import subprocess
import sys
import importlib.util
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


def test_normalize_ollama_version_returns_machine_parseable_value() -> None:
    module_path = Path("scripts/generate_odr_provenance.py")
    spec = importlib.util.spec_from_file_location("odr_provenance_module_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._normalize_ollama_version("ollama version is 0.17.4") == "0.17.4"
