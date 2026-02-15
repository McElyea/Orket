from __future__ import annotations

from scripts.check_gitea_state_pilot_readiness import evaluate_readiness


def test_readiness_passes_with_full_gitea_inputs() -> None:
    result = evaluate_readiness(
        {
            "state_backend_mode": "gitea",
            "pilot_enabled": True,
            "gitea_url": "https://gitea.local",
            "gitea_token": "secret",
            "gitea_owner": "acme",
            "gitea_repo": "orket",
        }
    )
    assert result["ready"] is True
    assert result["failures"] == []


def test_readiness_fails_when_mode_is_not_gitea() -> None:
    result = evaluate_readiness(
        {
            "state_backend_mode": "local",
            "pilot_enabled": True,
            "gitea_url": "https://gitea.local",
            "gitea_token": "secret",
            "gitea_owner": "acme",
            "gitea_repo": "orket",
        }
    )
    assert result["ready"] is False
    assert any("state_backend_mode" in item for item in result["failures"])


def test_readiness_fails_when_required_config_missing() -> None:
    result = evaluate_readiness(
        {
            "state_backend_mode": "gitea",
            "pilot_enabled": False,
            "gitea_url": "",
            "gitea_token": "",
            "gitea_owner": "acme",
            "gitea_repo": "",
        }
    )
    assert result["ready"] is False
    assert "gitea_url" in result["missing_config_keys"]
    assert "gitea_token" in result["missing_config_keys"]
    assert "gitea_repo" in result["missing_config_keys"]
    assert any("ORKET_ENABLE_GITEA_STATE_PILOT" in item for item in result["failures"])
