import importlib


def test_webhook_server_import_does_not_require_secrets(monkeypatch):
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    assert module.app is not None
    assert module.create_webhook_app(require_config=False) is module.app


def test_validate_signature_logs_reject_by_default_when_secret_missing(monkeypatch):
    """Layer: contract. Verifies missing webhook secrets are logged as reject-by-default, not auth-disabled."""
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)
    events = []

    def _capture(event_name, payload, workspace, role=None):
        events.append((event_name, payload, workspace, role))

    monkeypatch.setattr(module, "log_event", _capture)

    assert module.validate_signature(b"{}", "sig") is False
    assert events[0][0] == "webhook"
    assert events[0][1]["message"] == "GITEA_WEBHOOK_SECRET not set. All webhooks will be rejected."
