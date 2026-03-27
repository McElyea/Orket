import importlib
import contextlib
import os
from pathlib import Path


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


@contextlib.contextmanager
def _unset_pytest_marker():
    original = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["PYTEST_CURRENT_TEST"] = original


def test_create_webhook_app_reports_all_missing_required_env_vars(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)

    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)
    env_file = tmp_path / ".env"
    env_file.write_text("", encoding="utf-8")
    monkeypatch.setattr("orket.settings.ENV_FILE", env_file)
    monkeypatch.setattr("orket.settings._ENV_LOADED", False)

    with _unset_pytest_marker():
        try:
            module.create_webhook_app(require_config=True)
        except RuntimeError as exc:
            message = str(exc)
        else:
            raise AssertionError("Expected RuntimeError when required webhook env vars are missing.")

    assert "GITEA_WEBHOOK_SECRET" in message
    assert "GITEA_ADMIN_PASSWORD" in message


def test_create_webhook_app_loads_required_env_from_dotenv(monkeypatch, tmp_path: Path):
    module = importlib.import_module("orket.webhook_server")
    module = importlib.reload(module)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "GITEA_WEBHOOK_SECRET=test-secret\nGITEA_ADMIN_PASSWORD=test-admin\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("orket.settings.ENV_FILE", env_file)
    monkeypatch.setattr("orket.settings._ENV_LOADED", False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.setattr(module.webhook_handler, "_get", lambda: object())

    with _unset_pytest_marker():
        app = module.create_webhook_app(require_config=True)

    assert app is module.app
