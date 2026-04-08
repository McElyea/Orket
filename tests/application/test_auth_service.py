from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt


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
    monkeypatch.delenv("ORKET_AUTH_TOKEN_EXPIRE_MINUTES", raising=False)

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)
    token = reloaded.create_access_token({"sub": "operator"})

    assert isinstance(token, str)
    assert token
    claims = jwt.get_unverified_claims(token)
    assert claims["sub"] == "operator"
    assert isinstance(claims["jti"], str)
    exp = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    remaining = exp - datetime.now(UTC)
    assert timedelta(minutes=55) <= remaining <= timedelta(minutes=65)


def test_auth_service_create_access_token_honors_expiry_override(monkeypatch):
    """Layer: unit. Verifies token expiry can be reduced explicitly through env configuration."""
    monkeypatch.setenv("ORKET_AUTH_SECRET", "test-secret")
    monkeypatch.setenv("ORKET_AUTH_TOKEN_EXPIRE_MINUTES", "5")

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)
    token = reloaded.create_access_token({"sub": "operator"})
    claims = jwt.get_unverified_claims(token)
    exp = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
    remaining = exp - datetime.now(UTC)

    assert timedelta(minutes=4) <= remaining <= timedelta(minutes=6)


def test_auth_service_verify_access_token_rejects_revoked_token(monkeypatch, tmp_path):
    """Layer: unit. Verifies JWT verification fails closed once a token `jti` is blocklisted."""
    monkeypatch.setenv("ORKET_AUTH_SECRET", "test-secret")

    import orket.services.auth_service as auth_service

    reloaded = importlib.reload(auth_service)
    token = reloaded.create_access_token({"sub": "operator"})
    claims = jwt.get_unverified_claims(token)
    blocklist = reloaded.TokenBlocklist(tmp_path / "auth_token_blocklist.sqlite3")
    blocklist.revoke(claims["jti"])

    with pytest.raises(ValueError, match="revoked"):
        reloaded.verify_access_token(token, blocklist=blocklist)
