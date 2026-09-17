"""Layer: integration. Real ASGI WebSocket routes and startup over captured application inputs."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from orket.interfaces.api import create_api_app

pytestmark = pytest.mark.integration


@pytest.mark.parametrize('mode', ['compat', 'enforce'])
@pytest.mark.parametrize('route', ['/ws/events', '/ws/interactions/captured'])
def test_websocket_authentication_retains_app_key_and_mode(tmp_path, monkeypatch, mode, route):
    monkeypatch.setenv('ORKET_DISABLE_SANDBOX', '1')
    monkeypatch.setenv('ORKET_STREAM_EVENTS_V1', 'true')
    monkeypatch.setenv('ORKET_DURABLE_ROOT', str(tmp_path/'.orket/durable'))
    monkeypatch.setenv('ORKET_OUTWARD_PIPELINE_DB_PATH', str(tmp_path/'outward.db'))
    environment = {'ORKET_API_KEY': 'captured-key', 'ORKET_API_SECURITY_MODE': mode, 'ORKET_ENV': 'local'}
    app = create_api_app(project_root=tmp_path, environment=environment)
    environment.update(ORKET_API_KEY='changed-key', ORKET_API_SECURITY_MODE='enforce' if mode == 'compat' else 'compat')
    monkeypatch.setenv('ORKET_API_KEY', 'changed-key')
    with TestClient(app) as client:
        with client.websocket_connect(route, headers={'X-API-Key': 'captured-key'}):
            pass
        for key in ('changed-key', 'incorrect-key'):
            with pytest.raises(WebSocketDisconnect) as denied, client.websocket_connect(
                route+'?api_key=captured-key', headers={'X-API-Key': key},
            ):
                pass
            assert denied.value.code == 4403
        if mode == 'compat':
            with client.websocket_connect(route+'?api_key=captured-key'):
                pass
        else:
            with pytest.raises(WebSocketDisconnect) as denied, client.websocket_connect(route+'?api_key=captured-key'):
                pass
            assert denied.value.code == 4403
    assert app.state.api_runtime_context.closed
    assert app.state.api_runtime_context.active_request_count == 0


def test_startup_rejects_captured_insecure_nonlocal_settings_after_environment_change(tmp_path, monkeypatch):
    app = create_api_app(project_root=tmp_path, environment={
        'ORKET_ENV': 'production', 'ORKET_API_SECURITY_PROFILE': 'dev', 'ORKET_ALLOW_INSECURE_NO_API_KEY': 'true',
    })
    monkeypatch.setenv('ORKET_ENV', 'local')
    monkeypatch.delenv('ORKET_ALLOW_INSECURE_NO_API_KEY', raising=False)
    with pytest.raises(RuntimeError, match='forbidden'), TestClient(app):
        pass
    assert app.state.api_runtime_context.closed
