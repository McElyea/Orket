"""Real direct pipeline construction must retain explicit registry settings."""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from orket.decision_nodes.builtins import DefaultToolStrategyNode
from orket.runtime.execution.execution_pipeline import ExecutionPipeline
from orket.settings import load_user_settings, set_runtime_settings_context

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _configuration(root):
    path = root / "model" / "organization.json"
    raw = json.dumps({"name": "File organization", "vision": "Registry inputs", "ethos": "Truth"}).encode()
    await asyncio.to_thread(path.write_bytes, raw)
    return path, raw


def _inputs(root, selected, preferences):
    environment = {key: value for key, value in os.environ.items()
                   if not (key.startswith("ORKET_") and key.endswith("_NODE"))}
    environment.pop("ORKET_ORG_NAME", None)
    environment.update(ORKET_DISABLE_SANDBOX="1", ORKET_DURABLE_ROOT=str(root / ".orket" / "durable"))
    return RuntimeConstructionInputs(root, environment, json.dumps(selected), preferences)


def _bind_ambient(settings):
    set_runtime_settings_context(user_settings=settings, user_preferences={}, environment={})


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
@pytest.mark.parametrize("ambient_name", ["chosen", "other"], ids=["same", "different"])
async def test_pipeline_registries_use_selected_snapshot(
    test_root, workspace, db_path, preferences, ambient_name,
):
    """Layer: integration. Actual configuration and initialized store binding use one supplied selection."""
    path, raw = await _configuration(test_root)
    selected = {"ORKET_TOOL_STRATEGY_NODE": "chosen", "ORKET_ORG_NAME": "Captured organization"}
    ambient = {"ORKET_TOOL_STRATEGY_NODE": ambient_name, "ORKET_ORG_NAME": "Ambient organization"}
    inputs = _inputs(test_root, selected, preferences)
    _bind_ambient(ambient)
    owner = None
    try:
        async with ExecutionPipeline.open(
            workspace, config_root=test_root, db_path=db_path, construction_inputs=inputs,
        ) as owner:
            await owner.initialize()
            assert owner.runtime_context.construction_inputs is inputs
            assert owner.org.name == "Captured organization"
            assert owner.user_settings == selected
            registries = (owner.decision_nodes, owner.sandbox_orchestrator.decision_nodes,
                          owner.orchestrator.decision_nodes)
            assert len({id(registry) for registry in registries}) == 3
            for registry in registries:
                chosen, other = DefaultToolStrategyNode(), DefaultToolStrategyNode()
                registry.register_tool_strategy("chosen", chosen)
                registry.register_tool_strategy("other", other)
                assert registry.resolve_tool_strategy(owner.org) is chosen
            assert owner.db_path == db_path
            scope = {"runtime_db": owner.db_path}
            assert owner.runtime_context.storage_binding.request_scope("registry-input-probe", scope) == scope
            assert not await asyncio.to_thread(Path(owner.db_path).exists)
        assert owner._closed
    finally:
        if owner is not None and not owner._closed:
            await owner.close()
    assert load_user_settings() == ambient
    assert inputs.user_settings() == selected and inputs.user_preferences_json == preferences
    assert await asyncio.to_thread(path.read_bytes) == raw


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
async def test_pipeline_refuses_retired_setting_in_selected_inputs_before_store_construction(
    test_root, workspace, db_path, preferences,
):
    """Layer: integration. Explicit retired configuration cannot be lost to ambient defaults."""
    path, raw = await _configuration(test_root)
    selected = {"ORKET_MODEL_CLIENT_NODE": "retired-selected"}
    inputs = _inputs(test_root, selected, preferences)
    _bind_ambient({})
    owner = None
    try:
        with pytest.raises(ValueError, match="ORKET_MODEL_CLIENT_NODE is retired"):
            async with ExecutionPipeline.open(
                workspace, config_root=test_root, db_path=db_path, construction_inputs=inputs,
            ) as owner:
                pass
    finally:
        if owner is not None:
            await owner.close()
    assert owner is None
    assert not await asyncio.to_thread(Path(db_path).exists)
    assert load_user_settings() == {}
    assert inputs.user_settings() == selected and inputs.user_preferences_json == preferences
    assert await asyncio.to_thread(path.read_bytes) == raw


@pytest.mark.parametrize("preferences", [None, "{}"], ids=["selective", "complete"])
async def test_pipeline_empty_selected_settings_do_not_admit_ambient_retired_configuration(
    test_root, workspace, db_path, preferences,
):
    """Layer: integration. Empty explicit settings remain authoritative through nested owners."""
    path, raw = await _configuration(test_root)
    ambient = {"ORKET_MODEL_CLIENT_NODE": "retired-ambient"}
    inputs = _inputs(test_root, {}, preferences)
    _bind_ambient(ambient)
    owner = None
    try:
        async with ExecutionPipeline.open(
            workspace, config_root=test_root, db_path=db_path, construction_inputs=inputs,
        ) as owner:
            await owner.initialize()
            assert owner.org.name == "File organization"
            assert owner.user_settings == {}
            assert owner.runtime_context.construction_inputs is inputs
            assert owner.sandbox_orchestrator.decision_nodes is not owner.orchestrator.decision_nodes
        assert owner._closed
    finally:
        if owner is not None and not owner._closed:
            await owner.close()
    assert load_user_settings() == ambient
    assert inputs.user_preferences_json == preferences
    assert await asyncio.to_thread(path.read_bytes) == raw
