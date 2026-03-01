from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync

from .conftest import base_config


def test_loop_detects_cycle_with_entry_step_zero(tmp_path: Path) -> None:
    config = base_config(rulesystem_id="loop", episodes=1)
    config["artifact_policy"] = "all"
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    root = Path(result["artifact_root"])
    episode = json.loads((root / "episodes" / "episode_00000" / "episode.json").read_text(encoding="utf-8"))
    assert episode["terminal_result"]["reason"] == "cycle_detected"
    anomaly = episode["anomalies"][0]
    assert anomaly["type"] == "cycle_detected"
    assert anomaly["cycle_entry_step"] == 0
    assert anomaly["cycle_length"] == 2


def test_loop_run_is_deterministic(tmp_path: Path) -> None:
    config = base_config(rulesystem_id="loop", episodes=5)
    left = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path / "a")
    right = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path / "b")
    assert left["summary_digest"] == right["summary_digest"]
    assert left["run_digest"] == right["run_digest"]
