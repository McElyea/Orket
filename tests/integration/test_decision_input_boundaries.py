"""Layer: integration. Real file/HTTP effects through captured application composition."""

import asyncio
import json
from dataclasses import FrozenInstanceError
from functools import partial
from types import SimpleNamespace

import pytest

from orket.application.services.decision_context_service import capture_loop_policy_inputs
from orket.application.services.decision_node_registry import DecisionNodeRegistry, build_decision_node_registry
from orket.application.services.model_client_factory import ModelClientFactory
from orket.application.services.runtime_result_lifetime import create_runtime_owner
from orket.application.services.toolbox import ToolBox
from orket.core.contracts.decision_inputs import ModelClientOptions, ToolSelectionInput
from orket.decision_nodes.builtins import DefaultLoaderStrategyNode, DefaultOrchestrationLoopPolicyNode
from orket.runtime.config.config_loader import ConfigLoader
from orket.settings import set_runtime_settings_context


@pytest.mark.parametrize(
    "name",
    ["TOOL_STRATEGY", "API_RUNTIME", "SANDBOX_POLICY", "LOADER_STRATEGY", "EXECUTION_RUNTIME", "ORCHESTRATION_LOOP"],
)
def test_registry_captures_environment_and_stored_settings(monkeypatch, name):
    """Layer: contract. Resolution cannot observe later mutation of either input source."""
    key, slot = "ORKET_" + name + "_NODE", name.lower()
    set_runtime_settings_context(user_settings={key: "stored"})
    environment = {key: "captured"}
    registry = build_decision_node_registry(environment=environment)
    stored = build_decision_node_registry(environment={})
    selected, stale = object(), object()
    for instance in (registry, stored):
        getattr(instance, "register_" + slot)("captured", selected)
        getattr(instance, "register_" + slot)("stored", stale)
    environment[key] = "default"
    monkeypatch.setenv(key, "default")
    set_runtime_settings_context(user_settings={key: "default"})
    org = SimpleNamespace(process_rules={slot + "_node": "default"})
    assert getattr(registry, "resolve_" + slot)(org) is selected
    assert getattr(stored, "resolve_" + slot)(org) is stale


def test_loop_limits_are_immutable_captured_values(monkeypatch):
    """Layer: contract. The same captured values produce the same limits after mutation."""
    environment = {"ORKET_ORCHESTRATOR_CONCURRENCY": "2", "ORKET_CONTEXT_WINDOW": "6"}
    org = SimpleNamespace(process_rules={"orchestrator_max_iterations": "28"})
    inputs = capture_loop_policy_inputs(org, environment)
    environment["ORKET_ORCHESTRATOR_CONCURRENCY"] = "9"
    monkeypatch.setenv("ORKET_ORCHESTRATOR_CONCURRENCY", "9")
    org.process_rules["orchestrator_max_iterations"] = "99"
    node = DefaultOrchestrationLoopPolicyNode()
    assert (node.concurrency_limit(inputs), node.max_iterations(inputs), node.context_window(inputs)) == (2, 28, 6)
    with pytest.raises(FrozenInstanceError):
        inputs.concurrency = "9"


@pytest.mark.parametrize("source", ["environment", "stored", "constructor", "organization", "module"])
def test_retired_model_client_strategy_configuration_is_rejected(source):
    """Layer: contract. Removed executable strategy configuration never silently falls back."""
    registry = DecisionNodeRegistry()
    with pytest.raises(ValueError, match="retired|Unsupported"):
        if source == "environment":
            build_decision_node_registry(environment={"ORKET_MODEL_CLIENT_NODE": "custom"})
        elif source == "stored":
            set_runtime_settings_context(user_settings={"ORKET_MODEL_CLIENT_NODE": "custom"})
            build_decision_node_registry(environment={})
        elif source == "constructor":
            DecisionNodeRegistry(settings={"ORKET_MODEL_CLIENT_NODE": "custom"})
        elif source == "organization":
            registry.resolve_planner(SimpleNamespace(process_rules={"model_client_node": "custom"}))
        else:
            registry.register_module_nodes("custom", {"model_client": object()})


@pytest.mark.asyncio
@pytest.mark.parametrize("selection", ["callable", "mapping", "unknown", "duplicate"])
async def test_tool_strategy_cannot_substitute_executable_bindings(tmp_path, selection):
    marker = tmp_path / "unexpected-write.txt"

    def injected(*_args, **_kwargs):
        marker.write_text("unauthorized binding", encoding="utf-8")
        return {"ok": True}

    class Strategy:
        def select_tools(self, inputs):
            assert isinstance(inputs, ToolSelectionInput)
            assert all(isinstance(name, str) for name in inputs.available_names)
            with pytest.raises(FrozenInstanceError):
                inputs.available_names = ()
            return {
                "callable": (injected,),
                "mapping": {"read_file": injected},
                "unknown": ("custom_effect",),
                "duplicate": ("read_file", "read_file"),
            }[selection]

    registry = DecisionNodeRegistry(settings={"ORKET_TOOL_STRATEGY_NODE": "custom"})
    registry.register_tool_strategy("custom", Strategy())
    toolbox = ToolBox({}, str(tmp_path), [], db_path=str(tmp_path / "cards.db"), decision_nodes=registry)
    with pytest.raises(ValueError, match="Tool strategy"):
        await toolbox.execute("read_file", {"path": "source.txt"})
    assert not marker.exists()


@pytest.mark.asyncio
async def test_loader_owns_overrides_and_captures_environment_before_io(tmp_path, monkeypatch):
    config = tmp_path / "config"
    config.mkdir()
    original = {
        "name": "Original",
        "vision": "Vision",
        "ethos": "Truth",
        "branding": {},
        "architecture": {},
        "contact": {"email": "test@example.com"},
        "departments": ["core"],
    }
    file = config / "organization.json"
    file.write_text(json.dumps(original), encoding="utf-8")

    class Strategy(DefaultLoaderStrategyNode):
        def apply_organization_overrides(self, *_args):
            raise AssertionError("retired mutation callback was invoked")

    registry = DecisionNodeRegistry(settings={"ORKET_LOADER_STRATEGY_NODE": "custom"})
    registry.register_loader_strategy("custom", Strategy())
    loader = ConfigLoader(tmp_path, decision_nodes=registry)
    entered, release = asyncio.Event(), asyncio.Event()
    observe = loader._exists

    async def held(path):
        entered.set()
        await release.wait()
        return await observe(path)

    monkeypatch.setattr(loader, "_exists", held)
    monkeypatch.setenv("ORKET_ORG_NAME", "Captured")
    operation = asyncio.create_task(loader.load_organization_async())
    try:
        await asyncio.wait_for(entered.wait(), timeout=5)
        monkeypatch.setenv("ORKET_ORG_NAME", "Changed")
        release.set()
        organization = await operation
        assert organization.name == "Captured"
        assert json.loads(file.read_text(encoding="utf-8")) == original
    finally:
        release.set()
        await asyncio.gather(operation, return_exceptions=True)


@pytest.mark.asyncio
async def test_application_model_factory_uses_captured_http_target(monkeypatch):
    requests, owners, failures = [], set(), []

    async def respond(reader, writer):
        task = asyncio.current_task()
        owners.add(task)
        try:
            header = await reader.readuntil(b"\r\n\r\n")
            line, *fields = header.decode().split("\r\n")
            length = next((int(f.split(":", 1)[1]) for f in fields if f.lower().startswith("content-length:")), 0)
            body = await reader.readexactly(length) if length else b""
            requests.append((line, json.loads(body) if body else None))
            payload = (
                {"data": [{"id": "fixture"}]}
                if line.startswith("GET /v1/models ")
                else {"choices": [{"message": {"content": "observed response"}}], "usage": {}}
            )
            encoded = json.dumps(payload).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
                + f"Content-Length: {len(encoded)}\r\nConnection: close\r\n\r\n".encode()
                + encoded
            )
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError) as exc:
            failures.append(type(exc).__name__)
        finally:
            writer.close()
            await writer.wait_closed()
            owners.remove(task)

    server = await asyncio.start_server(respond, "127.0.0.1", 0)
    environment = {
        "ORKET_LLM_PROVIDER": "openai_compat",
        "ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL": "false",
        "ORKET_PROVIDER_RUNTIME_AUTO_LOAD_LOCAL_MODEL": "false",
        "ORKET_LLM_OPENAI_BASE_URL": f"http://127.0.0.1:{server.sockets[0].getsockname()[1]}/v1",
    }
    factory = ModelClientFactory(environment)
    environment["ORKET_LLM_OPENAI_BASE_URL"] = "http://127.0.0.1:1/v1"
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "invalid-after-capture")
    provider = await create_runtime_owner(partial(factory.create_provider, "fixture", ModelClientOptions(0.25, 30.0)),
                                          label="test-provider-construction")
    client = factory.create_client(provider)
    try:
        response = await client.complete([{"role": "user", "content": "hello"}])
        assert response.content == "observed response"
        sent = [body for line, body in requests if line.startswith("POST /v1/chat/completions ")]
        assert len(sent) == 1 and sent[0]["model"] == "fixture"
        assert sent[0]["temperature"] == 0.25
    finally:
        await client.close()
        assert provider.client.is_closed
        server.close()
        await server.wait_closed()
        if owners:
            await asyncio.wait_for(asyncio.gather(*owners), timeout=5)
        assert not owners and not failures
