from __future__ import annotations

import json
from pathlib import Path

from orket.rulesim.workload import run_rulesim_v0_sync


def _golden_config() -> dict[str, object]:
    return {
        "schema_version": "rulesim_v0",
        "rulesystem_id": "golden_determinism",
        "run_seed": 42,
        "episodes": 100,
        "max_steps": 10,
        "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "artifact_policy": "none",
    }


def test_golden_summary_digest_stable(tmp_path: Path) -> None:
    result = run_rulesim_v0_sync(input_config=_golden_config(), workspace_path=tmp_path / "a")
    expected = (Path(__file__).parent / "fixtures" / "golden_summary_digest.txt").read_text(encoding="utf-8").strip()
    assert result["summary_digest"] == expected


def test_golden_repeatable_across_runs(tmp_path: Path) -> None:
    left = run_rulesim_v0_sync(input_config=_golden_config(), workspace_path=tmp_path / "a")
    right = run_rulesim_v0_sync(input_config=_golden_config(), workspace_path=tmp_path / "b")
    assert left["summary_digest"] == right["summary_digest"]
    left_summary = json.loads((Path(left["artifact_root"]) / "summary.json").read_text(encoding="utf-8"))
    right_summary = json.loads((Path(right["artifact_root"]) / "summary.json").read_text(encoding="utf-8"))
    assert left_summary == right_summary
