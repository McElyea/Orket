"""Integration: standalone composition retains explicit registry settings snapshots."""
from __future__ import annotations

import asyncio
import json
from functools import partial
from pathlib import Path

import pytest

from orket.adapters.execution.owned_io import run_owned_thread
from orket.adapters.storage.async_repositories import AsyncRunLedgerRepository
from orket.application.services.decision_node_registry import DecisionNodeRegistry
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.application.services.runtime_result_lifetime import open_runtime_owner
from orket.decision_nodes.builtins import DefaultLoaderStrategyNode, DefaultToolStrategyNode
from orket.runtime.config.config_loader import ConfigLoader
from orket.runtime.config.runtime_context import OrketRuntimeContext
from orket.settings import load_user_settings, set_runtime_settings_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _configuration(root):
    path = root / "model" / "organization.json"
    raw = json.dumps({"name": "File organization", "vision": "Registry inputs", "ethos": "Truth"}).encode()
    await asyncio.to_thread(path.write_bytes, raw)
    return path, raw


def _ambient(settings):
    set_runtime_settings_context(user_settings=settings, user_preferences={}, environment={})


def _context_factory(root, workspace, db_path, selected, preferences):
    inputs = RuntimeConstructionInputs(root, {}, json.dumps(selected), preferences)
    factory = partial(OrketRuntimeContext.from_env, workspace_root=workspace,
        db_path=db_path, config_root=root, config_loader_factory=ConfigLoader,
        run_ledger_repo=AsyncRunLedgerRepository(db_path), construction_inputs=inputs)
    return inputs, factory


def _tool_choice(registry):
    chosen, other = DefaultToolStrategyNode(), DefaultToolStrategyNode()
    registry.register_tool_strategy("chosen", chosen)
    registry.register_tool_strategy("other", other)
    return registry.resolve_tool_strategy(), chosen


def _loader_choice(loader):
    chosen, other = DefaultLoaderStrategyNode(), DefaultLoaderStrategyNode()
    loader.decision_nodes.register_loader_strategy("chosen", chosen)
    loader.decision_nodes.register_loader_strategy("other", other)
    return loader.decision_nodes.resolve_loader_strategy(), chosen


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
@pytest.mark.parametrize("ambient_name", ["chosen", "other"], ids=["same", "different"])
async def test_standalone_context_registries_keep_selected_inputs(
    test_root, workspace, db_path, preferences, ambient_name,
):
    """Layer: integration. Native context and actual loader registries share selected values."""
    path, raw = await _configuration(test_root)
    selected = {"ORKET_TOOL_STRATEGY_NODE": "chosen", "ORKET_ORG_NAME": "Captured organization"}
    ambient = {"ORKET_TOOL_STRATEGY_NODE": ambient_name, "ORKET_ORG_NAME": "Ambient organization"}
    _ambient(ambient)
    inputs, factory = _context_factory(test_root, workspace, db_path, selected, preferences)
    async with open_runtime_owner(factory, label="standalone-context-fixture") as context:
        await context.initialize()
        assert context.construction_inputs is inputs and context.user_settings == selected
        assert context.org.name == "Captured organization"
        assert context.decision_nodes is not context.loader.decision_nodes
        for registry in (context.decision_nodes, context.loader.decision_nodes):
            actual, chosen = _tool_choice(registry)
            assert actual is chosen
        assert context.db_path == db_path
        scope = {"runtime_db": context.db_path}
        assert context.storage_binding.request_scope("registry-probe", scope) == scope
        assert not await asyncio.to_thread(Path(context.db_path).exists)
    assert load_user_settings() == ambient
    assert inputs.user_settings() == selected and inputs.user_preferences_json == preferences
    assert await asyncio.to_thread(path.read_bytes) == raw


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
async def test_standalone_context_refuses_selected_retired_setting(
    test_root, workspace, db_path, preferences,
):
    """Layer: integration. Explicit retired configuration refuses before runtime DB creation."""
    path, raw = await _configuration(test_root)
    selected = {"ORKET_MODEL_CLIENT_NODE": "retired-selected"}
    _ambient({})
    inputs, factory = _context_factory(test_root, workspace, db_path, selected, preferences)
    context = None
    with pytest.raises(ValueError, match="ORKET_MODEL_CLIENT_NODE is retired"):
        async with open_runtime_owner(factory, label="standalone-context-refusal") as context:
            pass
    assert context is None and not await asyncio.to_thread(Path(db_path).exists)
    assert load_user_settings() == {} and inputs.user_settings() == selected
    assert await asyncio.to_thread(path.read_bytes) == raw


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
async def test_standalone_context_empty_settings_exclude_ambient_retired_setting(
    test_root, workspace, db_path, preferences,
):
    """Layer: integration. Empty selected settings reach context and loader independently."""
    path, raw = await _configuration(test_root)
    ambient = {"ORKET_MODEL_CLIENT_NODE": "retired-ambient"}
    _ambient(ambient)
    inputs, factory = _context_factory(test_root, workspace, db_path, {}, preferences)
    async with open_runtime_owner(factory, label="standalone-context-empty") as context:
        await context.initialize()
        assert context.org.name == "File organization" and context.user_settings == {}
        assert context.construction_inputs is inputs
        scope = {"runtime_db": context.db_path}
        assert context.storage_binding.request_scope("registry-probe", scope) == scope
        assert not await asyncio.to_thread(Path(context.db_path).exists)
    assert load_user_settings() == ambient and inputs.user_settings() == {}
    assert await asyncio.to_thread(path.read_bytes) == raw


@pytest.mark.parametrize("ambient_name", ["chosen", "other"], ids=["same", "different"])
async def test_standalone_loader_registry_keeps_serialized_settings(test_root, ambient_name):
    """Layer: integration. Real configuration loading and registry selection retain supplied values."""
    path, raw = await _configuration(test_root)
    selected = {"ORKET_LOADER_STRATEGY_NODE": "chosen", "ORKET_ORG_NAME": "Captured organization"}
    ambient = {"ORKET_LOADER_STRATEGY_NODE": ambient_name, "ORKET_ORG_NAME": "Ambient organization"}
    _ambient(ambient)
    loader = await run_owned_thread(partial(ConfigLoader, test_root, user_settings=selected, environment={}),
                                   label="standalone-loader-fixture")
    selected.update(ORKET_LOADER_STRATEGY_NODE="other", ORKET_ORG_NAME="Mutated organization")
    actual, chosen = _loader_choice(loader)
    assert actual is chosen
    organization = await run_owned_thread(loader.load_organization, label="standalone-loader-read")
    assert organization.name == "Captured organization"
    assert json.loads(loader._user_settings)["ORKET_LOADER_STRATEGY_NODE"] == "chosen"
    assert load_user_settings() == ambient
    assert await asyncio.to_thread(path.read_bytes) == raw


async def test_standalone_loader_refuses_selected_retired_setting(test_root):
    """Layer: integration. Supplied retired setting refuses the actual native constructor."""
    path, raw = await _configuration(test_root)
    _ambient({})
    with pytest.raises(ValueError, match="ORKET_MODEL_CLIENT_NODE is retired"):
        await run_owned_thread(partial(ConfigLoader, test_root, environment={},
            user_settings={"ORKET_MODEL_CLIENT_NODE": "retired-selected"}), label="standalone-loader-refusal")
    assert load_user_settings() == {}
    assert await asyncio.to_thread(path.read_bytes) == raw


async def test_standalone_loader_empty_settings_exclude_ambient_retired_setting(test_root):
    """Layer: integration. Explicit empty settings preserve file defaults without ambient refusal."""
    path, raw = await _configuration(test_root)
    ambient = {"ORKET_MODEL_CLIENT_NODE": "retired-ambient"}
    _ambient(ambient)
    loader = await run_owned_thread(partial(ConfigLoader, test_root, environment={}, user_settings={}),
                                   label="standalone-loader-empty")
    organization = await run_owned_thread(loader.load_organization, label="standalone-loader-read")
    assert organization.name == "File organization" and json.loads(loader._user_settings) == {}
    assert load_user_settings() == ambient
    assert await asyncio.to_thread(path.read_bytes) == raw


async def test_standalone_loader_omitted_settings_keep_existing_ambient_selection(test_root):
    """Layer: integration. Omission keeps the existing registry bootstrap behavior."""
    _ambient({"ORKET_LOADER_STRATEGY_NODE": "chosen"})
    loader = await run_owned_thread(partial(ConfigLoader, test_root, environment={}),
                                   label="standalone-loader-omitted")
    actual, chosen = _loader_choice(loader)
    assert actual is chosen and loader._user_settings is None


async def test_standalone_loader_supplied_registry_keeps_existing_precedence(test_root):
    """Layer: integration. Explicit registry identity bypasses registry construction as before."""
    path, raw = await _configuration(test_root)
    _ambient({"ORKET_MODEL_CLIENT_NODE": "retired-ambient"})
    registry = DecisionNodeRegistry(settings={})
    loader = await run_owned_thread(partial(ConfigLoader, test_root, decision_nodes=registry,
        environment={}, user_settings={"ORKET_MODEL_CLIENT_NODE": "retired-selected"}),
        label="standalone-loader-supplied")
    assert loader.decision_nodes is registry
    organization = await run_owned_thread(loader.load_organization, label="standalone-loader-read")
    assert organization.name == "File organization"
    assert await asyncio.to_thread(path.read_bytes) == raw
