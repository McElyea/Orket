from __future__ import annotations

import pytest

from orket.workloads.registry import is_builtin_workload, validate_builtin_workload_start


@pytest.mark.unit
def test_rulesim_is_registered_builtin_workload() -> None:
    assert is_builtin_workload("rulesim_v0")


@pytest.mark.contract
def test_rulesim_validate_start_accepts_minimal_valid_config() -> None:
    validate_builtin_workload_start(
        workload_id="rulesim_v0",
        input_config={
            "rulesystem_id": "loop",
            "run_seed": 1,
            "episodes": 1,
            "max_steps": 2,
            "agents": [{"id": "agent_0", "strategy": "random_uniform", "params": {}}],
            "scenario": {"turn_order": ["agent_0"]},
        },
        turn_params={},
    )

