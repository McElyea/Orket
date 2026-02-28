from __future__ import annotations

import json
from pathlib import Path

from orket.reforger.runbundle import deterministic_run_stamp, prepare_run_dirs, write_manifest


def test_runbundle_required_files_and_manifest_stability(tmp_path: Path) -> None:
    run_stamp = deterministic_run_stamp(
        mode_id="truth_only",
        model_id="fake",
        seed=7,
        budget=3,
        baseline_digest="abc123",
    )
    run_root = tmp_path / "runs" / run_stamp
    dirs = prepare_run_dirs(run_root)
    for key in ("inputs", "baseline_resolved", "candidates", "eval", "diff"):
        assert dirs[key].is_dir()

    payload = {
        "tool_version": "0.0.0",
        "seed": 7,
        "timestamps": {"generated_at_utc": "T1"},
        "digests": {"mode": "a", "baseline_pack": "b", "suite": "c", "run_bundle": "d"},
    }
    write_manifest(dirs["manifest"], payload)
    first = json.loads(dirs["manifest"].read_text(encoding="utf-8"))
    payload2 = dict(payload)
    payload2["timestamps"] = {"generated_at_utc": "T2"}
    write_manifest(dirs["manifest"], payload2)
    second = json.loads(dirs["manifest"].read_text(encoding="utf-8"))
    assert first["seed"] == second["seed"]
    assert first["digests"] == second["digests"]
    assert first["timestamps"] != second["timestamps"]

