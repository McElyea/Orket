"""Real authored asset reads retain application-generated identities in validated values."""
from __future__ import annotations

import asyncio
import json
import re

import pytest
from pydantic import ValidationError

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.runtime.config.config_loader import ConfigLoader
from orket.schema import EnvironmentConfig, EpicConfig, RoleConfig

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class RefuseIdentities(RuntimeInputService):
    def create_card_id(self):
        raise OSError("identity source unavailable")

    def create_verification_scenario_id(self):
        raise OSError("identity source unavailable")


async def _asset(tmp_path, category, payload):
    path = tmp_path / "config" / category / "authored.json"
    await asyncio.to_thread(path.parent.mkdir, parents=True, exist_ok=True)
    await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")
    return path


async def test_real_epic_loading_materializes_and_reloads_retained_nested_ids(tmp_path):
    original = {"team": "team", "environment": "dev", "stories": [{"summary": "Issue", "verification": {
        "scenarios": [{"description": "Check", "input_data": {}, "expected_output": True}]}}]}
    path = await _asset(tmp_path, "epics", original)
    loader = ConfigLoader(tmp_path)
    value = await loader.load_asset_async("epics", "authored", EpicConfig)
    assert re.fullmatch("[0-9a-f]{32}", value.id)
    assert re.fullmatch("[0-9a-f]{32}", value.issues[0].id)
    assert re.fullmatch("[0-9a-f]{4}", value.issues[0].verification.scenarios[0].id)
    assert json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8")) == original
    await asyncio.to_thread(path.write_text, value.model_dump_json(), encoding="utf-8")
    retained = await ConfigLoader(tmp_path, runtime_inputs=RefuseIdentities()).load_asset_async("epics", "authored", EpicConfig)
    assert retained.model_dump() == value.model_dump()


async def test_real_role_loading_propagates_identity_failure_without_rewriting_source(tmp_path):
    original = {"summary": "Builder", "description": "Build"}
    path = await _asset(tmp_path, "roles", original)
    with pytest.raises(OSError, match="identity source unavailable"):
        await ConfigLoader(tmp_path, runtime_inputs=RefuseIdentities()).load_asset_async("roles", "authored", RoleConfig)
    assert json.loads(await asyncio.to_thread(path.read_text, encoding="utf-8")) == original


async def test_real_environment_loaders_both_reject_unknown_keys(tmp_path):
    await _asset(tmp_path, "environments", {"name": "dev", "model": "model", "obsolete": True})
    loader = ConfigLoader(tmp_path)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        await loader.load_asset_async("environments", "authored", EnvironmentConfig)
    with pytest.raises(ValueError, match="E_ENVIRONMENT_CONFIG_UNKNOWN_KEYS:obsolete"):
        await loader.load_environment_asset_async("authored")
