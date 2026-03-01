from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def test_biased_first_player_greedy_flags_skew_and_dominance(tmp_path: Path) -> None:
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "biased_first_player",
        "run_seed": 13,
        "episodes": 100,
        "max_steps": 5,
        "agents": [
            {
                "id": "agent_0",
                "strategy": "greedy_heuristic",
                "params": {"score_map": {"win": 10, "pass": 0}},
            },
            {"id": "agent_1", "strategy": "random_uniform", "params": {}},
        ],
        "scenario": {"turn_order": ["agent_0", "agent_1"]},
        "artifact_policy": "none",
    }
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    summary = json.loads((Path(result["artifact_root"]) / "summary.json").read_text(encoding="utf-8"))
    assert summary["win_rate"]["agent_0"] == 1.0
    hint_types = {row["type"] for row in summary.get("run_hints", [])}
    assert "dominance_hint" in hint_types
    assert "first_player_skew" in hint_types


def test_biased_first_player_random_is_balanced(tmp_path: Path) -> None:
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "biased_first_player",
        "run_seed": 13,
        "episodes": 1000,
        "max_steps": 5,
        "agents": [
            {"id": "agent_0", "strategy": "random_uniform", "params": {}},
            {"id": "agent_1", "strategy": "random_uniform", "params": {}},
        ],
        "scenario": {"turn_order": ["agent_0", "agent_1"]},
        "artifact_policy": "none",
    }
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    summary = json.loads((Path(result["artifact_root"]) / "summary.json").read_text(encoding="utf-8"))
    rate = float(summary["win_rate"]["agent_0"])
    assert 0.45 <= rate <= 0.55
    hint_types = {row["type"] for row in summary.get("run_hints", [])}
    assert "dominance_hint" not in hint_types
    assert "first_player_skew" not in hint_types

