from __future__ import annotations

import importlib

import pytest


def test_auth_service_import_does_not_require_secret(monkeypatch):
    """Layer: unit. Verifies auth service import does not fail when ORKET_AUTH_SECRET is unset."""
    monkeypatch.delenv("ORKET_AUTH_SECRET", raising=False)

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)

    assert reloaded.SECRET_KEY is None


def test_auth_service_create_access_token_requires_secret_at_call_time(monkeypatch):
    """Layer: unit. Verifies token creation fails closed when no auth secret is configured."""
    monkeypatch.delenv("ORKET_AUTH_SECRET", raising=False)

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)

    with pytest.raises(RuntimeError, match="ORKET_AUTH_SECRET"):
        reloaded.create_access_token({"sub": "operator"})


def test_auth_service_create_access_token_uses_env_secret(monkeypatch):
    """Layer: unit. Verifies token creation succeeds once the auth secret is configured."""
    monkeypatch.setenv("ORKET_AUTH_SECRET", "test-secret")

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)
    token = reloaded.create_access_token({"sub": "operator"})

    assert isinstance(token, str)
    assert token
