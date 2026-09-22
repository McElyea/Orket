"""Layer: integration. Real ProductFlow engine cleanup precedes command return."""

import asyncio

import pytest

from orket.orchestration.engine import OrchestrationEngine
from scripts.productflow import build_operator_review_package, productflow_support, run_replay_review

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("command", [build_operator_review_package, run_replay_review])
@pytest.mark.parametrize("close_failure", [False, True])
def test_productflow_refusal_closes_actual_engine_before_return(tmp_path, monkeypatch, command, close_failure):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(productflow_support, "REPO_ROOT", tmp_path)
    created, closed = [], []
    command_active = True
    original_init, original_close = OrchestrationEngine.__init__, OrchestrationEngine.close

    def construct(owner, *args, **kwargs):
        original_init(owner, *args, **kwargs)
        created.append(owner)

    async def close(owner):
        await original_close(owner)
        closed.append(owner)
        if close_failure and command_active:
            await asyncio.to_thread((tmp_path / "missing-close-input").read_bytes)

    monkeypatch.setattr(OrchestrationEngine, "__init__", construct)
    monkeypatch.setattr(OrchestrationEngine, "close", close)
    output = tmp_path / "result.json"
    try:
        with pytest.raises(OSError if close_failure else ValueError):
            command.main(
                ["--run-id", "absent", "--workspace-root", str(tmp_path / "workspace"), "--output", str(output)]
            )
        assert len(created) == len(closed) == 1
        assert created[0]._closed and created[0]._pipeline._closed
        assert not output.exists()
    finally:
        command_active = False
        for owner in created:
            if not owner._closed:
                asyncio.run(original_close(owner))
