from __future__ import annotations

from scripts.run_gitea_state_rollout_gates import evaluate_gate_bundle


def test_gate_bundle_ready_when_all_gates_pass() -> None:
    summary = evaluate_gate_bundle(
        {
            "pilot_readiness": {"ok": True, "exit_code": 0},
            "hardening": {"ok": True, "exit_code": 0},
            "phase3": {"ok": True, "exit_code": 0},
        }
    )
    assert summary["ready"] is True
    assert summary["failures"] == []


def test_gate_bundle_not_ready_when_any_gate_fails() -> None:
    summary = evaluate_gate_bundle(
        {
            "pilot_readiness": {"ok": False, "exit_code": 1},
            "hardening": {"ok": True, "exit_code": 0},
            "phase3": {"ok": False, "exit_code": 1},
        }
    )
    assert summary["ready"] is False
    assert summary["failures"] == ["pilot_readiness", "phase3"]
