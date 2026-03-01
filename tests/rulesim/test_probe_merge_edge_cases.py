from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def test_probe_override_illegal_policy_inherits_rest_of_config(tmp_path: Path) -> None:
    result = run_rulesim_v0_sync(
        input_config={
            "schema_version": "rulesim_v0",
            "rulesystem_id": "illegal_action",
            "run_seed": 55,
            "episodes": 4,
            "max_steps": 4,
            "agents": [
                {"id": "agent_0", "strategy": "scripted", "params": {"sequence": [{"kind": "illegal_move"}]}},
            ],
            "scenario": {"turn_order": ["agent_0"]},
            "artifact_policy": "none",
            "illegal_action_policy": "substitute_first",
            "probes": [
                {
                    "probe_id": "p_invalid_terminal",
                    "episode_count": 3,
                    "variant_overrides": {"illegal_action_policy": "terminal_invalid_action"},
                }
            ],
        },
        workspace_path=tmp_path,
    )
    root = Path(result["artifact_root"])
    run_payload = json.loads((root / "run.json").read_text(encoding="utf-8"))
    probe_summary = json.loads((root / "probes" / "p_invalid_terminal" / "summary.json").read_text(encoding="utf-8"))
    assert run_payload["illegal_action_policy"] == "substitute_first"
    assert probe_summary["episodes"] == 3
    assert probe_summary["terminal_reason_distribution"]["invalid_action"] == 3

