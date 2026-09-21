"""Actual witness command refusal closes its runtime before any bundle publication."""
import asyncio

import pytest

from orket.orchestration.engine import OrchestrationEngine
from scripts.productflow import productflow_support
from scripts.proof.build_trusted_run_witness_bundle import main

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("close_failure", [False, True])
def test_witness_refusal_retains_required_engine_cleanup(tmp_path, monkeypatch, close_failure):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(productflow_support, "REPO_ROOT", tmp_path)
    closed = []
    command_active = True
    original = OrchestrationEngine.close

    async def close(owner):
        if owner._closed:
            return await original(owner)
        await original(owner)
        closed.append(owner)
        if close_failure and command_active:
            await asyncio.to_thread((tmp_path / "missing-close-input").read_bytes)

    monkeypatch.setattr(OrchestrationEngine, "close", close)
    output = tmp_path / "bundle.json"
    expected = OSError if close_failure else ValueError
    try:
        with pytest.raises(expected, match=None if close_failure else "productflow_runs_root_missing"):
            main(["--run-id", "absent", "--workspace-root", str(tmp_path / "workspace"), "--output", str(output)])
    finally:
        command_active = False
    assert len(closed) == 1 and closed[0]._closed and closed[0]._pipeline._closed
    assert not output.exists()
