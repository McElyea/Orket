from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def _summary_for(strategy: str, params: dict, tmp_path: Path, suffix: str) -> dict:
    result = run_rulesim_v0_sync(
        input_config={
            "schema_version": "rulesim_v0",
            "rulesystem_id": "biased_first_player",
            "run_seed": 44,
            "episodes": 500,
            "max_steps": 5,
            "agents": [
                {"id": "agent_0", "strategy": strategy, "params": params},
                {"id": "agent_1", "strategy": "random_uniform", "params": {}},
            ],
            "scenario": {"turn_order": ["agent_0", "agent_1"]},
            "artifact_policy": "none",
        },
        workspace_path=tmp_path / suffix,
    )
    return json.loads((Path(result["artifact_root"]) / "summary.json").read_text(encoding="utf-8"))


def test_strategy_profiles_are_meaningfully_different(tmp_path: Path) -> None:
    greedy = _summary_for("greedy_heuristic", {"score_map": {"win": 10, "pass": 0}}, tmp_path, "greedy")
    random_u = _summary_for("random_uniform", {}, tmp_path, "random")
    greedy_win = float(greedy["win_rate"]["agent_0"])
    random_win = float(random_u["win_rate"]["agent_0"])
    assert greedy_win >= 0.95
    assert 0.40 <= random_win <= 0.60
    assert (greedy_win - random_win) >= 0.35
    greedy_hist = greedy["action_key_histogram"]
    random_hist = random_u["action_key_histogram"]
    assert int(greedy_hist.get("pass", 0)) == 0
    assert int(random_hist.get("pass", 0)) > 0
