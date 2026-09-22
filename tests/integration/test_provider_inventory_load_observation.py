"""Layer: integration. Real child CLI execution; controlled model-state observations."""
import asyncio
import json
import sys
from pathlib import Path

import pytest

from orket.runtime.config import provider_runtime_inventory as inventory
from orket.runtime.config.provider_runtime_target import resolve_provider_runtime_target

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("mode,allow_load", [("ack_only", True), ("observed", True), ("observed", False)])
async def test_model_load_success_requires_observed_loaded_inventory(tmp_path, monkeypatch, mode, allow_load):
    script = Path(__file__).with_name("provider_inventory_cli_worker.py")
    state = tmp_path/"model-state.json"
    original = inventory._run_command_sync
    commands = []

    def run(cmd, *, timeout_s, cwd, environment):
        assert cmd[0] == "lms"
        commands.append(tuple(cmd))
        return original([sys.executable, str(script), str(state), mode, *cmd[1:]],
                        timeout_s=timeout_s, cwd=cwd, environment=environment)

    monkeypatch.setattr(inventory, "_run_command_sync", run)
    result = await resolve_provider_runtime_target(
        provider="lmstudio", requested_model="fixture", base_url="http://127.0.0.1:1234/v1",
        timeout_s=5, auto_select_model=False, auto_load_local_model=allow_load,
        model_load_timeout_s=5, model_ttl_sec=600, environment={},
    )
    loaded = mode == "observed" and allow_load
    assert result.status == ("OK" if loaded else "BLOCKED")
    assert result.auto_load_attempted is allow_load
    assert result.auto_load_performed is loaded
    assert result.loaded_models_after == (("fixture",) if loaded else ())
    assert sum(command[1] == "load" for command in commands) == int(allow_load)
    if allow_load:
        observed = json.loads(await asyncio.to_thread(state.read_text))
        assert observed == {"loads": 1, "loaded": loaded}
    else:
        assert not await asyncio.to_thread(state.exists)
