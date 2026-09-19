"""Contract controls use synthetic native observations, not live process proof."""
from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessCancelled, CommandProcessSupervisor
from orket.core.contracts.owned_command import OwnedCommandResult
from orket.extensions.sdk_workload_runner import SdkSubprocessExecutionUncertain, run_sdk_workload_in_subprocess
from tests.helpers.sdk_lifetime import sdk_request

pytestmark = [pytest.mark.contract, pytest.mark.asyncio]
COMPLETED = OwnedCommandResult(0, b"", b"", "completed", True, True, "fixture", 1, 2, 3, ())


@pytest.mark.parametrize("mode", ["cancel-unconfirmed", "cleanup-unconfirmed", "capture-incomplete",
    "malformed-json", "wrong-exit", "missing-ok", "invalid-workload", "invalid-report"])
async def test_unknown_sdk_observations_preserve_exchange(tmp_path, monkeypatch, mode):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))
    lifetime = COMPLETED
    if mode in {"cancel-unconfirmed", "cleanup-unconfirmed"}:
        lifetime = replace(COMPLETED, reason="cleanup_unconfirmed", cleanup_confirmed=False)
    if mode == "capture-incomplete":
        lifetime = replace(COMPLETED, reason="capture_incomplete", capture_complete=False)
    payload = {"ok": True, "workload_result": {"ok": True}, "capability_report": {}}
    if mode == "wrong-exit":
        payload["ok"] = False
    elif mode == "missing-ok":
        del payload["ok"]
    elif mode == "invalid-workload":
        payload["workload_result"] = []
    elif mode == "invalid-report":
        payload["capability_report"] = []

    async def native(_owner, argv, **_kwargs):
        raw = b"broken json" if mode == "malformed-json" else json.dumps(payload).encode()
        await asyncio.to_thread(Path(argv[-1]).write_bytes, raw)
        if mode == "cancel-unconfirmed":
            raise CommandProcessCancelled(lifetime)
        return lifetime

    monkeypatch.setattr(CommandProcessSupervisor, "run", native)
    with pytest.raises(SdkSubprocessExecutionUncertain) as caught:
        await run_sdk_workload_in_subprocess(**sdk_request(tmp_path))
    assert caught.value.lifetime is lifetime
    assert caught.value.exchange_path.is_dir()
    assert (caught.value.exchange_path / "request.json").is_file()
    assert not (tmp_path / "sdk-effect").exists()


@pytest.mark.parametrize("deadline", [0, -1, float("nan"), float("inf")])
async def test_invalid_sdk_deadline_cannot_dispatch(tmp_path, deadline):
    with pytest.raises(ValueError, match="E_SDK_SUBPROCESS_TIMEOUT_INVALID"):
        await run_sdk_workload_in_subprocess(**sdk_request(tmp_path), timeout_seconds=deadline)
    assert not (tmp_path / "sdk-effect").exists()


async def test_sdk_diagnostic_failure_preserves_execution_uncertainty(tmp_path, monkeypatch):
    exchanges = tmp_path / "exchanges"
    exchanges.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(exchanges))

    async def native(_owner, _argv, **_kwargs):
        return COMPLETED

    def refuse(*_args):
        raise PermissionError("controlled diagnostic failure")

    monkeypatch.setattr(CommandProcessSupervisor, "run", native)
    monkeypatch.setattr("orket.extensions.sdk_workload_runner.log_event", refuse)
    with pytest.raises(SdkSubprocessExecutionUncertain) as caught:
        await run_sdk_workload_in_subprocess(**sdk_request(tmp_path))
    assert caught.value.phase == "lifetime-observation"
    assert caught.value.lifetime is COMPLETED
    assert isinstance(caught.value.__cause__, PermissionError)
    assert isinstance(caught.value.diagnostic_error, PermissionError)
    assert caught.value.exchange_path.is_dir()
