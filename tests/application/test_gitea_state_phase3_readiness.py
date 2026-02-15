from __future__ import annotations

from scripts.check_gitea_state_phase3_readiness import evaluate_phase3_readiness


def test_phase3_readiness_passes_when_gates_and_targets_are_green() -> None:
    result = evaluate_phase3_readiness(
        pilot_ready=True,
        hardening_ready=True,
        test_exits={
            "tests/adapters/test_gitea_state_adapter.py": 0,
            "tests/adapters/test_gitea_state_adapter_contention.py": 0,
            "tests/adapters/test_gitea_state_multi_runner_simulation.py": 0,
            "tests/application/test_gitea_state_worker.py": 0,
            "tests/application/test_gitea_state_worker_coordinator.py": 0,
        },
    )
    assert result["ready"] is True
    assert result["failures"] == []


def test_phase3_readiness_fails_when_gate_or_target_fails() -> None:
    result = evaluate_phase3_readiness(
        pilot_ready=False,
        hardening_ready=True,
        test_exits={
            "tests/adapters/test_gitea_state_adapter.py": 0,
            "tests/adapters/test_gitea_state_adapter_contention.py": 1,
            "tests/adapters/test_gitea_state_multi_runner_simulation.py": 0,
            "tests/application/test_gitea_state_worker.py": 0,
            "tests/application/test_gitea_state_worker_coordinator.py": 0,
        },
    )
    assert result["ready"] is False
    assert "pilot readiness gate is not ready" in result["failures"]
    assert "tests/adapters/test_gitea_state_adapter_contention.py exit_code=1" in result["failures"]
