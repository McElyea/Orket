from __future__ import annotations

import asyncio
import importlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient


def test_api_import_constructs_only_the_compatibility_default_owner() -> None:
    """Layer: contract. Import creates one default owner while optional services remain lazy."""
    module = importlib.import_module("orket.interfaces.api")
    project_root = module._project_root()
    context = module.app.state.api_runtime_context

    assert context.project_root == project_root
    assert module._get_engine() is module.engine
    assert module._get_runtime_state() is module.runtime_state
    assert module._get_api_runtime_node() is module.api_runtime_node
    assert context.stream_bus is None
    assert context.interaction_manager is None
    assert context.extension_manager is None


def test_factory_owns_distinct_runtime_graphs_for_distinct_roots(tmp_path: Path) -> None:
    """Layer: integration. Factory results retain independent application-owned runtime graphs."""
    module = importlib.import_module("orket.interfaces.api")
    default_context = module.app.state.api_runtime_context
    root_a = (tmp_path / "workspace_a").resolve()
    root_b = (tmp_path / "workspace_b").resolve()

    app_a = module.create_api_app(project_root=root_a)
    app_b = module.create_api_app(project_root=root_b)
    context_a = app_a.state.api_runtime_context
    context_b = app_b.state.api_runtime_context

    context_a.stream_bus = module._get_stream_bus(app_a)
    context_b.stream_bus = module._get_stream_bus(app_b)
    context_a.interaction_manager = module._get_interaction_manager(app_a)
    context_b.interaction_manager = module._get_interaction_manager(app_b)
    context_a.extension_manager = module._get_extension_manager(app_a)
    context_b.extension_manager = module._get_extension_manager(app_b)
    context_a.extension_runtime_service = module._get_extension_runtime_service(app_a)
    context_b.extension_runtime_service = module._get_extension_runtime_service(app_b)

    assert app_a is not app_b
    assert app_a is not module.app
    assert app_b is not module.app
    assert context_a is not context_b
    assert context_a.project_root == root_a
    assert context_b.project_root == root_b
    assert app_a.state.outbound_policy_config is not app_b.state.outbound_policy_config
    for attribute in (
        "api_runtime_node",
        "runtime_state",
        "api_runtime_host",
        "engine",
        "stream_bus",
        "interaction_manager",
        "extension_manager",
        "extension_runtime_service",
    ):
        assert getattr(context_a, attribute) is not getattr(context_b, attribute)
    assert module.app.state.api_runtime_context is default_context

    engine_b = context_b.engine
    asyncio.run(context_a.close())
    assert context_a.closed is True
    assert context_b.closed is False
    assert context_b.engine is engine_b
    asyncio.run(context_b.close())


def test_concurrent_requests_observe_their_own_app_root(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Concurrent HTTP requests resolve the root from their ASGI app."""
    module = importlib.import_module("orket.interfaces.api")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    root_a = (tmp_path / "workspace_a").resolve()
    root_b = (tmp_path / "workspace_b").resolve()
    app_a = module.create_api_app(project_root=root_a)
    app_b = module.create_api_app(project_root=root_b)

    app_a.add_api_route("/_isolation/root", lambda: {"root": str(module._project_root())}, methods=["GET"])
    app_b.add_api_route("/_isolation/root", lambda: {"root": str(module._project_root())}, methods=["GET"])

    with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
        with ThreadPoolExecutor(max_workers=2) as pool:
            response_a = pool.submit(client_a.get, "/_isolation/root")
            response_b = pool.submit(client_b.get, "/_isolation/root")

        assert response_a.result().json() == {"root": str(root_a)}
        assert response_b.result().json() == {"root": str(root_b)}


def test_lifespan_closes_engine_and_tracked_tasks_once(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. App teardown cancels transport tasks and closes its engine once."""
    module = importlib.import_module("orket.interfaces.api")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    created_app = module.create_api_app(project_root=tmp_path)
    context = created_app.state.api_runtime_context
    original_engine = context.engine

    class RecordingEngine:
        def __init__(self) -> None:
            self.initialize_calls = 0
            self.close_calls = 0

        async def initialize(self) -> None:
            self.initialize_calls += 1

        async def close(self) -> None:
            self.close_calls += 1

    recording_engine = RecordingEngine()
    asyncio.run(original_engine.close())
    context.engine = recording_engine

    with TestClient(created_app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert context.active_background_task_count == 1

    assert recording_engine.initialize_calls == 1
    assert recording_engine.close_calls == 1
    assert context.active_background_task_count == 0
    assert context.closed is True

    asyncio.run(context.close())
    assert recording_engine.close_calls == 1


def test_repeated_app_lifecycles_leave_no_tracked_tasks(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Repeated construction and teardown leaves every owner closed and task-free."""
    module = importlib.import_module("orket.interfaces.api")
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    contexts = []

    for index in range(3):
        created_app = module.create_api_app(project_root=tmp_path / f"workspace_{index}")
        context = created_app.state.api_runtime_context
        with TestClient(created_app) as client:
            assert client.get("/health").status_code == 200
        contexts.append(context)

    assert len({id(context) for context in contexts}) == 3
    assert all(context.closed for context in contexts)
    assert all(context.active_background_task_count == 0 for context in contexts)


def test_default_engine_alias_cannot_cross_into_created_app(tmp_path: Path, monkeypatch) -> None:
    """Layer: contract. The compatibility engine alias influences only the module-default app."""
    module = importlib.import_module("orket.interfaces.api")
    default_context = module.app.state.api_runtime_context
    previous_engine = default_context.engine
    created_app = module.create_api_app(project_root=tmp_path)
    created_context = created_app.state.api_runtime_context
    replacement_engine = object()

    monkeypatch.setattr(module, "engine", replacement_engine)

    assert module._get_engine() is replacement_engine
    assert default_context.engine is replacement_engine
    assert module._get_engine(created_app) is created_context.engine
    assert created_context.engine is not replacement_engine

    default_context.engine = previous_engine
    asyncio.run(created_context.close())
