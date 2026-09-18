"""Integration: captured authentication and rate admission through real ASGI requests."""

import pytest
from fastapi.testclient import TestClient

from tests.helpers.webhook import application, signed

pytestmark = pytest.mark.integration


def test_rate_limit_is_independent_for_each_application(tmp_path):
    first = application(tmp_path / "first", ORKET_RATE_LIMIT="1")
    second = application(tmp_path / "second", ORKET_RATE_LIMIT="1")
    with TestClient(first) as left, TestClient(second) as right:
        assert signed(left).status_code == 200
        response = signed(left)
        assert response.status_code == 429 and response.headers["Retry-After"] == "60"
        assert signed(right).status_code == 200
        assert signed(right).status_code == 429


@pytest.mark.parametrize("signature, detail", [(None, "Missing signature"), ("invalid", "Invalid signature")])
def test_signature_required_before_dispatch(tmp_path, signature, detail):
    with TestClient(application(tmp_path)) as client:
        headers = {"X-Gitea-Event": "ping"}
        if signature is not None:
            headers["X-Gitea-Signature"] = signature
        response = client.post("/webhook/gitea", json={}, headers=headers)
        assert response.status_code == 401 and response.json()["detail"] == detail


def test_test_endpoint_disabled_by_default(tmp_path):
    with TestClient(application(tmp_path)) as client:
        response = client.post("/webhook/test", json={})
        assert response.status_code == 403
        assert response.json()["detail"] == "Test webhook endpoint disabled"


def test_test_endpoint_requires_configured_auth(tmp_path):
    with TestClient(application(tmp_path, ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT="true")) as client:
        response = client.post("/webhook/test", json={})
        assert response.status_code == 403
        assert response.json()["detail"] == "Test webhook auth not configured"


@pytest.mark.parametrize("use_token", [False, True])
def test_test_endpoint_uses_captured_auth_with_token_priority(monkeypatch, tmp_path, use_token):
    app = application(
        tmp_path,
        ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT="true",
        ORKET_API_KEY="key",
        ORKET_WEBHOOK_TEST_TOKEN="token" if use_token else "",
    )
    monkeypatch.setenv("ORKET_API_KEY", "rotated")
    monkeypatch.setenv("ORKET_WEBHOOK_TEST_TOKEN", "rotated")
    with TestClient(app) as client:
        assert client.post("/webhook/test", json={}).status_code == 401
        headers = {"X-Webhook-Test-Token": "token"} if use_token else {"X-API-Key": "key"}
        response = client.post("/webhook/test", json={"event": "ping"}, headers=headers)
        assert response.status_code == 200 and response.json()["status"] == "ignored"
        if use_token:
            assert client.post("/webhook/test", json={}, headers={"X-API-Key": "key"}).status_code == 401


def test_health_reports_captured_rate_scope(tmp_path):
    with TestClient(application(tmp_path, ORKET_RATE_LIMIT="17", ORKET_WEBHOOK_WORKERS="3")) as client:
        assert client.get("/health").json() == {
            "status": "healthy",
            "rate_limit_scope": "per_application_per_process",
            "webhook_rate_limit_per_minute": 17,
            "worker_count_hint": 3,
        }
