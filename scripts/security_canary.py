from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@contextmanager
def _temp_env(overrides: dict[str, str | None]):
    original = {k: os.environ.get(k) for k in overrides}
    try:
        for key, value in overrides.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _assert(condition: bool, message: str):
    if not condition:
        raise RuntimeError(message)


def run_api_auth_canary():
    with _temp_env(
        {
            "ORKET_API_KEY": None,
            "ORKET_ALLOW_INSECURE_NO_API_KEY": "false",
        }
    ):
        module = importlib.import_module("orket.interfaces.api")
        module = importlib.reload(module)
        client = TestClient(module.app)
        response = client.get("/v1/version")
        _assert(response.status_code == 403, f"Expected 403 for /v1/version without key, got {response.status_code}")


def run_webhook_signature_canary():
    with _temp_env(
        {
            "GITEA_ADMIN_PASSWORD": "test-pass",
            "GITEA_WEBHOOK_SECRET": "test-secret",
            "ORKET_ENABLE_WEBHOOK_TEST_ENDPOINT": "false",
            "ORKET_API_KEY": None,
            "ORKET_WEBHOOK_TEST_TOKEN": None,
        }
    ):
        module = importlib.import_module("orket.webhook_server")
        module = importlib.reload(module)
        client = TestClient(module.app)
        body = {"action": "opened", "number": 1, "repository": {"full_name": "org/repo"}}

        missing_sig = client.post("/webhook/gitea", json=body, headers={"x-gitea-event": "pull_request"})
        _assert(missing_sig.status_code == 401, f"Expected 401 for missing signature, got {missing_sig.status_code}")

        test_ep = client.post("/webhook/test", json={"event": "pull_request_review", "payload": {}})
        _assert(test_ep.status_code == 403, f"Expected 403 for disabled /webhook/test, got {test_ep.status_code}")


def main():
    print("[security-canary] Running API auth canary")
    run_api_auth_canary()
    print("[security-canary] Running webhook signature canary")
    run_webhook_signature_canary()
    print("[security-canary] SUCCESS")


if __name__ == "__main__":
    main()
