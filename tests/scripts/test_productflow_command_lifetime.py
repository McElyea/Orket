"""Layer: integration. ProductFlow's controlled provider is never inference proof."""

import asyncio
import json

import pytest

from orket.orchestration.engine import OrchestrationEngine
from scripts.productflow import productflow_support, run_governed_write_file_flow
from scripts.proof import run_trusted_run_witness_campaign
from tests.helpers.turn_control_plane_clock import deterministic_turn_clock as deterministic_turn_clock

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("deterministic_turn_clock")]


@pytest.mark.parametrize("campaign", [False, True])
def test_productflow_command_closes_engine_before_publishing(tmp_path, monkeypatch, campaign):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(productflow_support, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(run_trusted_run_witness_campaign, "PROOF_RESULTS_ROOT", tmp_path / "results")
    command = run_trusted_run_witness_campaign if campaign else run_governed_write_file_flow
    created, execution_loops, cleanup_loops = [], [], []
    original_init, original_run, original_close = (
        OrchestrationEngine.__init__,
        OrchestrationEngine.run_card,
        OrchestrationEngine.close,
    )
    original_write = command.write_payload_with_diff_ledger

    def construct(owner, *args, **kwargs):
        original_init(owner, *args, **kwargs)
        created.append(owner)

    async def run(owner, *args, **kwargs):
        execution_loops.append(asyncio.get_running_loop())
        return await original_run(owner, *args, **kwargs)

    async def close(owner):
        if not owner._closed:
            cleanup_loops.append(asyncio.get_running_loop())
        return await original_close(owner)

    def publish(*args, **kwargs):
        assert created and all(owner._closed and owner._pipeline._closed for owner in created)
        return original_write(*args, **kwargs)

    monkeypatch.setattr(OrchestrationEngine, "__init__", construct)
    monkeypatch.setattr(OrchestrationEngine, "run_card", run)
    monkeypatch.setattr(OrchestrationEngine, "close", close)
    monkeypatch.setattr(command, "write_payload_with_diff_ledger", publish)
    output = tmp_path / "report.json"
    arguments = ["--workspace-root", str(tmp_path / "workspace"), "--output", str(output)]
    if campaign:
        arguments.extend(["--runs", "2"])
    try:
        code = command.main(arguments)
        payload = json.loads(output.read_text())
        assert code == 0 and payload["observed_result"] == "success"
        assert len(created) == len(execution_loops) == len(cleanup_loops) == (2 if campaign else 1)
        assert all(
            run_loop is close_loop and close_loop.is_closed()
            for run_loop, close_loop in zip(execution_loops, cleanup_loops, strict=True)
        )
    finally:
        for owner in created:
            if not owner._closed:
                asyncio.run(original_close(owner))
