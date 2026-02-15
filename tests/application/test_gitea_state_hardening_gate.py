from __future__ import annotations

from scripts.check_gitea_state_hardening import evaluate_hardening


def test_hardening_gate_passes_when_all_targets_green() -> None:
    result = evaluate_hardening(
        {
            "tests/adapters/test_gitea_state_adapter.py": 0,
            "tests/adapters/test_gitea_state_adapter_contention.py": 0,
        }
    )
    assert result["ready"] is True
    assert result["failures"] == []


def test_hardening_gate_fails_when_any_target_fails() -> None:
    result = evaluate_hardening(
        {
            "tests/adapters/test_gitea_state_adapter.py": 0,
            "tests/adapters/test_gitea_state_adapter_contention.py": 1,
        }
    )
    assert result["ready"] is False
    assert result["failures"] == [
        "tests/adapters/test_gitea_state_adapter_contention.py exit_code=1"
    ]
