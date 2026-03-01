from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def test_illegal_action_substitute_first_continues_episode(tmp_path: Path) -> None:
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "illegal_action",
        "run_seed": 9,
        "episodes": 1,
        "max_steps": 4,
        "agents": [
            {
                "id": "agent_0",
                "strategy": "scripted",
                "params": {"sequence": [{"kind": "illegal_move"}]},
            }
        ],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "all",
        "illegal_action_policy": "substitute_first",
    }
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    root = Path(result["artifact_root"])
    episode = json.loads((root / "episodes" / "episode_00000" / "episode.json").read_text(encoding="utf-8"))
    assert episode["terminal_result"]["reason"] == "draw"
    anomaly = episode["anomalies"][0]
    assert anomaly["type"] == "illegal_action_attempt"
    assert anomaly["attempted_action_cjson"] == '{"kind":"illegal_move"}'
    assert anomaly["legal_action_keys"] == ["pass", "move"]
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["illegal_action_rate"] == 1.0


def test_illegal_action_terminal_policy_stops_episode(tmp_path: Path) -> None:
    config = {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "illegal_action",
        "run_seed": 9,
        "episodes": 1,
        "max_steps": 4,
        "agents": [
            {
                "id": "agent_0",
                "strategy": "scripted",
                "params": {"sequence": [{"kind": "illegal_move"}]},
            }
        ],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "all",
        "illegal_action_policy": "terminal_invalid_action",
    }
    result = run_rulesim_v0_sync(input_config=config, workspace_path=tmp_path)
    root = Path(result["artifact_root"])
    episode = json.loads((root / "episodes" / "episode_00000" / "episode.json").read_text(encoding="utf-8"))
    assert episode["terminal_result"]["reason"] == "invalid_action"

