from __future__ import annotations

from scripts.decide_microservices_pilot import decide_from_unlock_report


def test_decision_enables_microservices_when_unlock_true() -> None:
    payload = {
        "unlocked": True,
        "failures": [],
        "recommended_default_builder_variant": "coder",
    }
    decision = decide_from_unlock_report(payload)
    assert decision["enable_microservices"] is True
    assert decision["recommended_env"]["ORKET_ENABLE_MICROSERVICES"] == "true"
    assert decision["unlock_failures"] == []


def test_decision_keeps_microservices_locked_when_unlock_false() -> None:
    payload = {
        "unlocked": False,
        "failures": ["pass_rate below threshold"],
    }
    decision = decide_from_unlock_report(payload)
    assert decision["enable_microservices"] is False
    assert decision["recommended_env"]["ORKET_ENABLE_MICROSERVICES"] == "false"
    assert "pass_rate below threshold" in decision["unlock_failures"][0]
