"""Real preview/filesystem observations through API strategy admission, without inference."""
import asyncio
import inspect
import json
from pathlib import Path

import pytest

from orket.adapters.storage.async_file_tools import AsyncFileTools
from orket.application.services.api_runtime_host_service import ApiRuntimeHostService
from orket.application.services.api_system_query_service import ApiSystemQueryService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.decision_nodes.api_runtime_strategy_node import DefaultApiRuntimeStrategyNode
from orket.interfaces.api import _invoke_async_method
from orket.interfaces.routers.system import RunAssetRequest, build_system_router

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def endpoint(path, root, node, host, **overrides):
    # Unused route dependencies stay absent; this fixture only admits the named route.
    dependencies = {name: None for name in inspect.signature(build_system_router).parameters}
    dependencies.update(project_root_getter=lambda: root, api_runtime_node_getter=lambda: node,
        runtime_host_getter=lambda: host, invoke_async_method=_invoke_async_method, **overrides)
    router = build_system_router(**dependencies)
    return next(route.endpoint for route in router.routes if route.path == path)


async def test_preview_invocation_survives_held_actual_builder_construction(tmp_path, monkeypatch):
    fs = AsyncFileTools(tmp_path)
    for name in ("requested", "replacement"):
        await fs.write_file(f"model/core/rocks/{name}.json", json.dumps({"id": name, "name": name, "epics": []}))
    proposal = {"method_name": "build_rock_preview", "args": ["requested", "core"]}
    class Retained(DefaultApiRuntimeStrategyNode):
        def resolve_preview_invocation(self, target, issue_id):
            with pytest.raises(TypeError):
                target["asset_name"] = "mutated"
            return proposal
    host = ApiRuntimeHostService(tmp_path, environment={"ORKET_DISABLE_SANDBOX": "1"})
    create = host.create_preview_builder
    entered, release = asyncio.Event(), asyncio.Event()
    async def held(root):
        builder = await create(root)
        entered.set()
        await release.wait()
        return builder
    monkeypatch.setattr(host, "create_preview_builder", held)
    preview = endpoint("/system/preview-asset", tmp_path, Retained(), host)
    operation = asyncio.create_task(preview(path="model/core/rocks/requested.json", issue_id=None))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        proposal["args"][0] = "replacement"
        proposal["method_name"] = "unsupported_replacement"
        release.set()
        result = await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert result == {"type": "rock", "id": "requested", "display_name": "requested", "description": None,
                      "milestone_tasks": None, "epics": []}


async def test_explorer_policy_cannot_rewrite_actual_filesystem_observations(tmp_path):
    fs = AsyncFileTools(tmp_path)
    await fs.write_file("observed.txt", "retained")
    observed = []
    class Inspect(DefaultApiRuntimeStrategyNode):
        def sort_explorer_items(self, items):
            observed.append(items)
            assert type(items) is tuple
            with pytest.raises(TypeError):
                items[0]["name"] = "invented.txt"
            return super().sort_explorer_items(items)
    queries = ApiSystemQueryService(tmp_path, environment={}, runtime_inputs=RuntimeInputService())
    result = await queries.explorer(".", Inspect())
    assert result == {"items": [{"name": "observed.txt", "is_dir": False, "ext": ".txt"}], "path": "."}
    assert len(observed) == 1 and await fs.read_file("observed.txt") == "retained"


async def test_run_invocation_survives_held_event_before_real_file_dispatch(tmp_path):
    # Controlled dispatcher; proves request/admission and file effects, not background run lifecycle.
    fs = AsyncFileTools(tmp_path)
    proposal = {"method_name": "write_file", "args": ["admitted.txt", "admitted"]}
    class Retained(DefaultApiRuntimeStrategyNode):
        def resolve_run_active_invocation(self, **kwargs):
            return proposal
    entered, release = asyncio.Event(), asyncio.Event()
    class Events:
        async def emit(self, name, payload):
            assert name == "api_run_active" and payload["method_name"] == "write_file"
            entered.set()
            await release.wait()
    async def dispatch(target, invocation, prefix, session_id):
        await _invoke_async_method(target, invocation, prefix)
    host = ApiRuntimeHostService(tmp_path, environment={"ORKET_DISABLE_SANDBOX": "1"})
    run = endpoint("/system/run-active", tmp_path, Retained(), host, engine_getter=lambda: fs,
        events_getter=Events, schedule_async_invocation_task=dispatch)
    operation = asyncio.create_task(run(RunAssetRequest(path="model/core/rocks/requested.json")))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        proposal["args"][:] = ["replacement.txt", "replacement"]
        release.set()
        await asyncio.wait_for(operation, 5)
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)
    assert await fs.read_file("admitted.txt") == "admitted"
    assert not await asyncio.to_thread(Path(tmp_path / "replacement.txt").exists)
