from __future__ import annotations

from typing import Any


def base_config(*, rulesystem_id: str, strategy: str = "random_uniform", episodes: int = 20) -> dict[str, Any]:
    return {
        "schema_version": "rulesim_v0",
        "rulesystem_id": rulesystem_id,
        "run_seed": 42,
        "episodes": episodes,
        "max_steps": 20,
        "agents": [{"id": "agent_0", "strategy": strategy, "params": {}}],
        "scenario": {"turn_order": ["agent_0"]},
        "ruleset": {},
        "artifact_policy": "none",
    }

