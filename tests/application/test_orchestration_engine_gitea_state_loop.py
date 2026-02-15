from __future__ import annotations

import pytest

from orket.orchestration.engine import OrchestrationEngine


@pytest.mark.asyncio
async def test_engine_delegates_run_gitea_state_loop_to_pipeline():
    engine = object.__new__(OrchestrationEngine)
    captured = {}

    class _FakePipeline:
        async def run_gitea_state_loop(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True, "summary": {"iterations": 1}}

    engine._pipeline = _FakePipeline()

    result = await engine.run_gitea_state_loop(
        worker_id="worker-9",
        fetch_limit=8,
        lease_seconds=20,
        renew_interval_seconds=3.0,
        max_iterations=2,
        max_idle_streak=2,
        max_duration_seconds=10.0,
        idle_sleep_seconds=0.1,
        summary_out="benchmarks/results/run.json",
    )
    assert result["ok"] is True
    assert captured["worker_id"] == "worker-9"
    assert captured["fetch_limit"] == 8
