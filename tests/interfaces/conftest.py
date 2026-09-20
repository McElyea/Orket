from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


class LazyApiTestClient:
    """Capture the test's inputs and enter the real lifespan on first explicit use."""

    def __init__(self, project_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self._project_root = project_root
        self._monkeypatch = monkeypatch
        self._app: Any = None
        self._client: TestClient | None = None

    @property
    def app(self) -> Any:
        self._live_client()
        return self._app

    def configure(self, *, project_root: Path) -> None:
        self.close()
        self._project_root = project_root

    def _live_client(self) -> TestClient:
        if self._client is None:
            import orket.interfaces.api as api_module
            import orket.state as state_module

            self._app = api_module.create_api_app(project_root=self._project_root)
            client = TestClient(self._app)
            client.__enter__()
            self._client = client
            api_module._ACTIVE_API_APP.set(self._app)
            self._monkeypatch.setattr(state_module, "runtime_state", self._app.state.api_runtime_context.runtime_state)
        return self._client

    def close(self) -> None:
        if self._client is None:
            return
        self._client.__exit__(None, None, None)
        self._client = None

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self._live_client().get(*args, **kwargs)

    def post(self, *args: Any, **kwargs: Any) -> Any:
        return self._live_client().post(*args, **kwargs)

    def put(self, *args: Any, **kwargs: Any) -> Any:
        return self._live_client().put(*args, **kwargs)

    def patch(self, *args: Any, **kwargs: Any) -> Any:
        return self._live_client().patch(*args, **kwargs)

    @contextmanager
    def websocket_connect(self, *args: Any, **kwargs: Any) -> Iterator[Any]:
        with self._live_client().websocket_connect(*args, **kwargs) as websocket:
            yield websocket


@pytest.fixture(autouse=True)
def fresh_api_client(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Replace opt-in module globals with a fresh lazy client per test."""
    if not hasattr(request.module, "client"):
        yield
        return

    import orket.interfaces.api as api_module
    if request.module.__name__.endswith("test_api_interactions"):
        monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    token = api_module._ACTIVE_API_APP.set(None)
    previous = request.module.client
    lazy_client = LazyApiTestClient(Path(api_module._resolve_default_project_root()), monkeypatch)
    request.module.client = lazy_client
    try:
        yield
    finally:
        lazy_client.close()
        api_module._ACTIVE_API_APP.reset(token)
        request.module.client = previous
