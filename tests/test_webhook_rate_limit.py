import importlib
import os

from fastapi.testclient import TestClient


def test_webhook_rate_limit(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("ORKET_RATE_LIMIT", "1")

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    async def _ok_handler(event_type, payload):
        return {"status": "ok", "message": "accepted"}

    module.webhook_handler.handle_webhook = _ok_handler
    module.validate_signature = lambda payload, signature: True

    client = TestClient(module.app)
    body = {"action": "opened", "number": 1, "repository": {"full_name": "org/repo"}}
    headers = {"x-gitea-event": "pull_request", "x-gitea-signature": "ignored"}

    first = client.post("/webhook/gitea", json=body, headers=headers)
    second = client.post("/webhook/gitea", json=body, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429


def test_webhook_requires_signature_header(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    called = {"count": 0}

    async def _ok_handler(event_type, payload):
        called["count"] += 1
        return {"status": "ok"}

    module.webhook_handler.handle_webhook = _ok_handler
    client = TestClient(module.app)
    body = {"action": "opened", "number": 1, "repository": {"full_name": "org/repo"}}

    response = client.post("/webhook/gitea", json=body, headers={"x-gitea-event": "pull_request"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing signature"
    assert called["count"] == 0


def test_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)
    module.validate_signature = lambda payload, signature: False
    client = TestClient(module.app)
    body = {"action": "opened", "number": 1, "repository": {"full_name": "org/repo"}}

    response = client.post(
        "/webhook/gitea",
        json=body,
        headers={"x-gitea-event": "pull_request", "x-gitea-signature": "invalid"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


def test_webhook_test_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")
    monkeypatch.delenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)
    client = TestClient(module.app)

    response = client.post("/webhook/test", json={"event": "pull_request_review", "payload": {}})
    assert response.status_code == 403
    assert response.json()["detail"] == "Test webhook endpoint disabled"


def test_webhook_test_endpoint_enabled_with_flag(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT", "true")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    async def _ok_handler(event_type, payload):
        return {"status": "ok", "message": "accepted"}

    module.webhook_handler.handle_webhook = _ok_handler
    client = TestClient(module.app)

    response = client.post(
        "/webhook/test",
        json={"event": "pull_request_review", "payload": {}},
        headers={"X-API-Key": "test-key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_test_endpoint_enabled_rejects_missing_auth(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT", "true")
    monkeypatch.delenv("ORKET_API_KEY", raising=False)
    monkeypatch.delenv("ORKET_WEBHOOK_TEST_TOKEN", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)
    client = TestClient(module.app)

    response = client.post("/webhook/test", json={"event": "pull_request_review", "payload": {}})
    assert response.status_code == 403
    assert response.json()["detail"] == "Test webhook auth not configured"


def test_webhook_test_endpoint_uses_test_token_when_configured(monkeypatch):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")
    monkeypatch.setenv("GITEA_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setenv("ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT", "true")
    monkeypatch.setenv("ORKET_WEBHOOK_TEST_TOKEN", "test-token")
    monkeypatch.delenv("ORKET_API_KEY", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    async def _ok_handler(event_type, payload):
        return {"status": "ok", "message": "accepted"}

    module.webhook_handler.handle_webhook = _ok_handler
    client = TestClient(module.app)

    unauthorized = client.post("/webhook/test", json={"event": "pull_request_review", "payload": {}})
    assert unauthorized.status_code == 401
    assert unauthorized.json()["detail"] == "Invalid test webhook token"

    authorized = client.post(
        "/webhook/test",
        json={"event": "pull_request_review", "payload": {}},
        headers={"X-Webhook-Test-Token": "test-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["status"] == "ok"
