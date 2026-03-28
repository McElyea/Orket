from __future__ import annotations

from scripts.acceptance.decide_microservices_pilot import decide_from_unlock_report


def _valid_unlock_criteria() -> dict[str, dict[str, object]]:
    return {
        "monolith_readiness_gate": {"ok": True, "failures": []},
        "matrix_stability": {"ok": True, "failures": []},
        "governance_stability": {"ok": True, "failures": []},
    }


def test_decision_enables_microservices_when_unlock_true() -> None:
    payload = {
        "unlocked": True,
        "criteria": _valid_unlock_criteria(),
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
        "criteria": {
            **_valid_unlock_criteria(),
            "matrix_stability": {"ok": False, "failures": ["pass_rate below threshold"]},
        },
        "failures": ["matrix_stability: pass_rate below threshold"],
    }
    decision = decide_from_unlock_report(payload)
    assert decision["enable_microservices"] is False
    assert decision["recommended_env"]["ORKET_ENABLE_MICROSERVICES"] == "false"
    assert "pass_rate below threshold" in decision["unlock_failures"][0]


# Layer: contract
def test_decision_rejects_malformed_unlock_report() -> None:
    payload = {
        "unlocked": True,
    }
    decision = decide_from_unlock_report(payload)
    assert decision["enable_microservices"] is False
    assert decision["recommended_env"]["ORKET_ENABLE_MICROSERVICES"] == "false"
    assert decision["unlock_failures"] == ["unlock report missing or invalid"]


# Layer: contract
def test_decision_rejects_inconsistent_unlock_report() -> None:
    payload = {
        "unlocked": True,
        "criteria": {
            **_valid_unlock_criteria(),
            "matrix_stability": {"ok": False, "failures": ["pass_rate below threshold"]},
        },
        "failures": ["stale failure"],
        "recommended_default_builder_variant": "coder",
    }
    decision = decide_from_unlock_report(payload)
    assert decision["enable_microservices"] is False
    assert decision["recommended_default_builder_variant"] is None
    assert decision["unlock_failures"] == ["unlock report missing or invalid"]
