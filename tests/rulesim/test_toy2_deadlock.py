from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def test_deadlock_records_agent_and_step(tmp_path: Path) -> None:
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "deadlock",
        "run_seed": 7,
        "episodes": 1,
        "max_steps": 5,
        "agents": [
            {"id": "agent_0", "strategy": "random_uniform", "params": {}},
            {"id": "agent_1", "strategy": "random_uniform", "params": {}},
        ],
        "scenario": {"turn_order": ["agent_0", "agent_1"]},
        "artifact_policy": "all",
    }
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    root = Path(result["artifact_root"])
    episode = json.loads((root / "episodes" / "episode_00000" / "episode.json").read_text(encoding="utf-8"))
    assert episode["terminal_result"]["reason"] == "deadlock"
    assert episode["terminal_result"]["winners"] == []
    anomaly = episode["anomalies"][0]
    assert anomaly["type"] == "deadlock"
    assert anomaly["agent_id"] == "agent_1"
    assert anomaly["step_index"] == 1

