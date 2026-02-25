import importlib


def test_webhook_server_import_does_not_require_secrets(monkeypatch):
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    assert module.app is not None
    assert module.create_webhook_app(require_config=False) is module.app

