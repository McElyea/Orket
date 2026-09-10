from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient


class LazyApiTestClient:
    """Open TestClient at request time so test-local env changes are visible."""

    def __init__(self, app: Any) -> None:
        self._app = app
        self._client: TestClient | None = None
        self._retired_contexts: list[Any] = []

    @property
    def app(self) -> Any:
        return self._app

    def configure(self, *, project_root: Path) -> None:
        import orket.interfaces.api as api_module

        self.close()
        previous_context = self._app.state.api_runtime_context
        if not previous_context.closed:
            self._retired_contexts.append(previous_context)
        self._app = api_module.create_api_app(project_root=project_root)
        api_module._ACTIVE_API_APP.set(self._app)

    @property
    def retired_contexts(self) -> tuple[Any, ...]:
        return tuple(self._retired_contexts)

    def _live_client(self) -> TestClient:
        if self._client is None:
            self._client = TestClient(self._app)
            self._client.__enter__()
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
    import orket.state as state_module
    if request.module.__name__.endswith("test_api_interactions"):
        monkeypatch.setenv("ORKET_STREAM_EVENTS_V1", "true")
    configured_app = api_module.create_api_app(project_root=Path(api_module._resolve_default_project_root()).resolve())
    monkeypatch.setattr(state_module, "runtime_state", configured_app.state.api_runtime_context.runtime_state)
    token = api_module._ACTIVE_API_APP.set(configured_app)
    previous = request.module.client
    lazy_client = LazyApiTestClient(configured_app)
    request.module.client = lazy_client
    try:
        yield
    finally:
        lazy_client.close()
        context = lazy_client.app.state.api_runtime_context
        if not context.closed:
            asyncio.run(context.close())
        for retired_context in lazy_client.retired_contexts:
            if not retired_context.closed:
                asyncio.run(retired_context.close())
        api_module._ACTIVE_API_APP.reset(token)
        request.module.client = previous
