"""Integration: real signals cannot strand reload owners in their event locks."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

import orket
from orket.application.services.command_process_supervisor import CommandProcessSupervisor

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]
HELPER = Path(__file__).resolve().parents[1] / "helpers" / "api_reload_signal_probe.py"


@pytest.mark.parametrize("owner_kind", ["parent", "worker"])
@pytest.mark.parametrize("held", [True, False], ids=["held", "free"])
async def test_reload_signal_handler_returns_while_event_condition_is_owned(
    tmp_path, owner_kind, held, record_property,
):
    namespace = await asyncio.to_thread(lambda: Path(orket.__file__).resolve().parent)
    module = namespace / "interfaces" / "api_reload_runtime.py"
    environment = dict(os.environ, ORKET_DISABLE_SANDBOX="1", PYTHONUTF8="1",
                       PYTHONIOENCODING="utf-8", PYTHONPATH=str(namespace.parent))
    condition = "held" if held else "free"
    owner = CommandProcessSupervisor(tmp_path, cancellation_event="reload_signal_probe_interrupted")
    result = await owner.run([sys.executable, str(HELPER), "--owner", owner_kind,
                              "--condition", condition], cwd=tmp_path, environment=environment,
                             timeout_seconds=5)
    output = (result.stdout + result.stderr).decode("utf-8", errors="replace")
    assert result.cleanup_confirmed and result.capture_complete, (result.lifetime(), output)
    assert result.reason == "completed" and result.returncode == 0, (result.lifetime(), output)
    payload = json.loads(result.stdout.decode("utf-8"))
    assert payload["observed_path"] == "primary" and payload["observed_result"] == "success"
    assert payload["owner"] == owner_kind and payload["condition"] == condition
    assert payload["signals_delivered"] == 2 and payload["pid"] > 0
    expected = (["signals_returned", "pause_stopped", "watcher_stop_published"] if owner_kind == "parent"
                else ["signals_returned", "lifespan_startup", "lifespan_shutdown", "serve_returned"])
    assert payload["completed_states"] == expected
    assert await asyncio.to_thread(lambda: Path(payload["module_origin"]).resolve() == module.resolve())
    actual_sha = await asyncio.to_thread(lambda: hashlib.sha256(module.read_bytes()).hexdigest())
    assert payload["module_sha256"] == actual_sha
    record_property("native_reload_signal_proof", json.dumps({"child": payload, "lifetime": result.lifetime()}))
