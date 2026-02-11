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
