"""Integration: real ASGI lifespan, captured configuration and HTTP client ownership."""

import contextlib
import importlib
import os

import pytest
from fastapi.testclient import TestClient

from orket.webhook_server import create_webhook_app
from tests.helpers.webhook import application, environment, signed

pytestmark = pytest.mark.integration


def test_import_does_not_construct_runtime_or_require_secrets(monkeypatch, tmp_path):
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)
    module = importlib.reload(importlib.import_module("orket.webhook_server"))
    assert not hasattr(module, "app") and not hasattr(module, "webhook_handler")
    app = module.create_webhook_app(require_config=False, project_root=tmp_path, environment={})
    assert app.state.webhook_runtime is None
    assert not list(tmp_path.iterdir())


def test_missing_secret_rejects_signed_ingress(tmp_path):
    app = create_webhook_app(
        require_config=False, project_root=tmp_path, environment=environment(tmp_path, GITEA_WEBHOOK_SECRET="")
    )
    with TestClient(app) as client:
        assert signed(client).status_code == 401
        assert signed(client, prefix=True).status_code == 401


@pytest.mark.parametrize("prefix", [False, True])
def test_native_gitea_digest_and_previously_admitted_prefixed_form(tmp_path, prefix):
    with TestClient(application(tmp_path)) as client:
        response = signed(client, prefix=prefix)
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
        assert signed(client, secret="wrong-secret", prefix=prefix).status_code == 401


def test_factory_reports_all_missing_required_inputs(tmp_path):
    with pytest.raises(RuntimeError) as raised:
        create_webhook_app(project_root=tmp_path, environment={})
    assert "GITEA_WEBHOOK_SECRET" in str(raised.value)
    assert "GITEA_ADMIN_PASSWORD" in str(raised.value)


@contextlib.contextmanager
def _unset_pytest_marker():
    original = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["PYTEST_CURRENT_TEST"] = original


def test_factory_loads_dotenv_before_capturing_configuration(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("GITEA_WEBHOOK_SECRET=test-secret\nGITEA_ADMIN_PASSWORD=test-admin\n", encoding="utf-8")
    monkeypatch.setattr("orket.settings.ENV_FILE", env_file)
    monkeypatch.setattr("orket.settings._ENV_LOADED", False)
    monkeypatch.delenv("GITEA_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("GITEA_ADMIN_PASSWORD", raising=False)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    with _unset_pytest_marker():
        app = create_webhook_app(project_root=tmp_path)
    with TestClient(app) as client:
        assert signed(client).status_code == 200
        assert app.state.webhook_runtime.gitea_password == "test-admin"


def test_distinct_apps_capture_roots_secrets_and_independent_resources(monkeypatch, tmp_path):
    invocation = tmp_path / "invocation"
    invocation.mkdir()
    monkeypatch.chdir(invocation)
    config = environment(tmp_path, GITEA_WEBHOOK_SECRET="first")
    first = create_webhook_app(project_root=tmp_path / "first", environment=config)
    config["GITEA_WEBHOOK_SECRET"] = "second"
    second = create_webhook_app(project_root=tmp_path / "second", environment=config)
    config["GITEA_WEBHOOK_SECRET"] = "third"
    monkeypatch.chdir(tmp_path)
    with TestClient(first) as left, TestClient(second) as right:
        a, b = first.state.webhook_runtime, second.state.webhook_runtime
        assert a is not b and a.client is not b.client and a.ingress is not b.ingress
        assert a.workspace == tmp_path / "first" and b.workspace == tmp_path / "second"
        assert a.configuration.invocation_root == invocation
        assert signed(left, secret="first").status_code == 200
        assert signed(left, secret="second").status_code == 401
        assert signed(right, secret="second").status_code == 200
        assert signed(right, secret="third").status_code == 401
    assert a.closed and b.closed and a.client.is_closed and b.client.is_closed


def test_shutdown_closes_client_and_refuses_later_requests_or_restart(tmp_path):
    app = application(tmp_path)
    with TestClient(app) as client:
        runtime = app.state.webhook_runtime
        assert not runtime.client.is_closed
        assert client.get("/health").status_code == 200
    assert runtime.closed and runtime.client.is_closed
    assert client.get("/health").status_code == 503
    with pytest.raises(RuntimeError, match="already started"), TestClient(app):
        pass


def test_http_is_unavailable_before_lifespan(tmp_path):
    client = TestClient(application(tmp_path))
    assert client.get("/health").status_code == 503
