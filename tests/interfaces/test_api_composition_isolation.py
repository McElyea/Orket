from __future__ import annotations

import ast
import asyncio
import importlib
import inspect
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient


def test_api_import_constructs_no_app_or_runtime_owner() -> None:
    """Layer: contract. Importing the router module has no application-owner side effects."""
    script = """
import json
from fastapi import FastAPI
import orket.interfaces.api as module
owner_names = [
    "app", "engine", "runtime_state", "api_runtime_node", "api_runtime_host",
    "stream_bus", "interaction_manager", "extension_manager", "extension_runtime_service",
]
print(json.dumps({
    "present_owner_names": [name for name in owner_names if hasattr(module, name)],
    "fastapi_instances": sum(isinstance(value, FastAPI) for value in vars(module).values()),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(completed.stdout)
    assert payload == {"present_owner_names": [], "fastapi_instances": 0}


def test_api_router_constructs_no_runtime_implementation() -> None:
    """Layer: contract. The transport module invokes composition but constructs no protected-layer class."""
    module = importlib.import_module("orket.interfaces.api")
    tree = ast.parse(inspect.getsource(module))
    protected_prefixes = (
        "orket.adapters",
        "orket.application",
        "orket.decision_nodes",
        "orket.extensions",
        "orket.kernel",
        "orket.orchestration",
    )
    protected_names = {
        alias.asname or alias.name: node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(protected_prefixes)
        for alias in node.names
        if (alias.asname or alias.name)[:1].isupper()
    }
    constructed = sorted(
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in protected_names
    )

    assert constructed == []


def test_factory_owns_distinct_runtime_graphs_for_distinct_roots(tmp_path: Path) -> None:
    """Layer: integration. Factory results retain independent application-owned runtime graphs."""
    module = importlib.import_module("orket.interfaces.api")
    root_a = (tmp_path / "workspace_a").resolve()
    root_b = (tmp_path / "workspace_b").resolve()

    app_a = module.create_api_app(project_root=root_a)
    app_b = module.create_api_app(project_root=root_b)
    context_a = app_a.state.api_runtime_context
    context_b = app_b.state.api_runtime_context

    assert app_a is not app_b
    assert context_a is not context_b
    assert context_a.project_root == root_a
    assert context_b.project_root == root_b
    assert app_a.state.outbound_policy_config is not app_b.state.outbound_policy_config
    assert context_a.runtime_state.event_queue is not context_b.runtime_state.event_queue
    assert context_a.extension_manager.catalog is not context_b.extension_manager.catalog
    for attribute in (
        "api_runtime_node",
        "runtime_state",
        "api_runtime_host",
        "engine",
        "stream_bus",
        "interaction_manager",
        "extension_manager",
        "extension_runtime_service",
        "outward_run_store",
        "outward_run_event_store",
        "outward_approval_store",
        "outward_run_service",
        "outward_approval_service",
        "outward_run_execution_service",
        "outward_run_inspection_service",
        "outward_ledger_service",
        "governed_agent_runtime",
    ):
        assert getattr(context_a, attribute) is not getattr(context_b, attribute)

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


def test_explicit_app_lookup_never_crosses_runtime_owners(tmp_path: Path) -> None:
    """Layer: contract. Explicit lookup always resolves the selected app-owned runtime."""
    module = importlib.import_module("orket.interfaces.api")
    app_a = module.create_api_app(project_root=tmp_path / "a")
    app_b = module.create_api_app(project_root=tmp_path / "b")

    assert module._get_engine(app_a) is app_a.state.api_runtime_context.engine
    assert module._get_engine(app_b) is app_b.state.api_runtime_context.engine
    assert module._get_engine(app_a) is not module._get_engine(app_b)

    asyncio.run(app_a.state.api_runtime_context.close())
    asyncio.run(app_b.state.api_runtime_context.close())
