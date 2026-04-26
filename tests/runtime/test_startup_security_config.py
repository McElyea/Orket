from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from orket.decision_nodes import api_runtime_strategy_node
from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket.interfaces.api import create_api_app
from orket.runtime.cors_config import resolve_cors_config
from orket.runtime.startup_checks import (
    REQUIRED_SECRET_PLACEHOLDERS,
    StartupConfigurationError,
    validate_required_secrets,
    warn_if_insecure_gitea_https,
)


def _safe_nonlocal_env() -> dict[str, str]:
    return {
        "ORKET_ENV": "production",
        "ORKET_ENCRYPTION_KEY": "0123456789abcdef0123456789abcdef",
        "SESSION_SECRET": "session-secret-for-test",
        "GITEA_WEBHOOK_SECRET": "webhook-secret-for-test",
        "ORKET_API_KEY": "api-key-for-test",
    }


@pytest.mark.unit
def test_validate_required_secrets_rejects_each_placeholder() -> None:
    """Layer: unit. Verifies non-local startup fails for each known required-secret placeholder."""
    for name, placeholders in REQUIRED_SECRET_PLACEHOLDERS.items():
        env = _safe_nonlocal_env()
        env[name] = sorted(placeholders)[0]

        with pytest.raises(StartupConfigurationError, match=name):
            validate_required_secrets(env)


@pytest.mark.unit
def test_validate_required_secrets_allows_local_placeholders() -> None:
    """Layer: unit. Verifies local development keeps placeholder examples usable."""
    env = {
        "ORKET_ENV": "local",
        "ORKET_ENCRYPTION_KEY": "your-32-byte-hex-key-here",
        "SESSION_SECRET": "your-session-secret-here",
        "GITEA_WEBHOOK_SECRET": "change-me-webhook-secret",
        "ORKET_API_KEY": "change-me-api-key",
    }

    validate_required_secrets(env)


@pytest.mark.integration
def test_api_lifespan_rejects_placeholder_secret_in_nonlocal_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Layer: integration. Verifies the FastAPI app refuses startup with non-local placeholder secrets."""
    for key, value in _safe_nonlocal_env().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("ORKET_API_KEY", "change-me-api-key")

    with pytest.raises(StartupConfigurationError, match="ORKET_API_KEY"):
        with TestClient(create_api_app(project_root=tmp_path)):
            pass


@pytest.mark.unit
def test_api_key_validation_uses_timing_safe_compare(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies API key equality routes through hmac.compare_digest."""
    calls: list[tuple[str, str]] = []

    def _fake_compare(left: str, right: str) -> bool:
        calls.append((left, right))
        return left == right

    monkeypatch.setattr(api_runtime_strategy_node.hmac, "compare_digest", _fake_compare)

    assert DefaultApiRuntimeStrategyNode().is_api_key_valid("expected", "expected") is True
    assert calls == [("expected", "expected")]


@pytest.mark.unit
def test_cors_config_denies_cross_origin_by_default() -> None:
    """Layer: unit. Verifies browser CORS starts closed unless explicit origins are configured."""
    config = resolve_cors_config({})

    assert config.allow_origins == []
    assert config.allow_credentials is False


@pytest.mark.unit
def test_cors_config_uses_explicit_origin_allowlist() -> None:
    """Layer: unit. Verifies ORKET_ALLOWED_ORIGINS is the only origin-opening surface."""
    config = resolve_cors_config({"ORKET_ALLOWED_ORIGINS": "http://localhost:5173, https://app.example"})

    assert config.allow_origins == ["http://localhost:5173", "https://app.example"]


@pytest.mark.unit
def test_insecure_gitea_https_warning_is_structured(caplog: pytest.LogCaptureFixture) -> None:
    """Layer: unit. Verifies insecure Gitea TLS bypass on HTTPS is reported at startup."""
    caplog.set_level("WARNING", logger="orket.runtime.startup_checks")

    assert warn_if_insecure_gitea_https(
        {"ORKET_GITEA_ALLOW_INSECURE": "true", "GITEA_URL": "https://localhost:3000"},
        logger=logging.getLogger("orket.runtime.startup_checks"),
    )
    assert any(record.message == "orket_gitea_insecure_tls_bypass_on_https" for record in caplog.records)
