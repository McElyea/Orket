"""Local webhook fixtures; no provider or outbound Gitea service is required."""

import hashlib
import hmac
import json

from orket.webhook_server import create_webhook_app


def environment(root, **overrides):
    return {
        "GITEA_ADMIN_PASSWORD": "test-password",
        "GITEA_WEBHOOK_SECRET": "test-secret",
        "GITEA_URL": "https://127.0.0.1:1",
        "ORKET_DURABLE_ROOT": str(root / "durable"),
        "ORKET_DISABLE_SANDBOX": "1",
        **overrides,
    }


def application(root, **overrides):
    return create_webhook_app(project_root=root, environment=environment(root, **overrides))


def signed(client, payload=None, *, secret="test-secret", delivery=None, event="ping", prefix=False):
    body = json.dumps(payload or {}, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Gitea-Event": event, "X-Gitea-Signature": ("sha256=" if prefix else "") + signature}
    if delivery is not None:
        headers["X-Gitea-Delivery"] = delivery
    return client.post("/webhook/gitea", content=body, headers=headers)
