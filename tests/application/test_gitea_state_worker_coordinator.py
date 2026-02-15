from __future__ import annotations

import asyncio
import json

import pytest

from orket.application.services.gitea_state_worker_coordinator import GiteaStateWorkerCoordinator


class _FakeWorker:
    def __init__(self, outcomes: list[bool]):
        self._outcomes = list(outcomes)
        self.calls = 0
        self.work_fns = []
        self.fetch_limits = []

    async def run_once(self, *, work_fn, fetch_limit: int = 1):
        self.calls += 1
        self.work_fns.append(work_fn)
        self.fetch_limits.append(fetch_limit)
        if self._outcomes:
            return self._outcomes.pop(0)
        return False


@pytest.mark.asyncio
async def test_run_stops_on_max_iterations_and_reports_summary():
    worker = _FakeWorker([True, False, True])
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        max_iterations=3,
        max_idle_streak=10,
        max_duration_seconds=60.0,
    )

    async def _work(_card):
        return {"ok": True}

    summary = await coordinator.run(work_fn=_work)
    assert summary["iterations"] == 3
    assert summary["consumed_count"] == 2
    assert summary["idle_count"] == 1
    assert summary["stop_reason"] == "max_iterations"
    assert summary["elapsed_ms"] >= 0


@pytest.mark.asyncio
async def test_run_stops_on_max_idle_streak():
    worker = _FakeWorker([False, False, False])
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        max_iterations=10,
        max_idle_streak=2,
        max_duration_seconds=60.0,
    )

    async def _work(_card):
        return {"ok": True}

    summary = await coordinator.run(work_fn=_work)
    assert summary["iterations"] == 2
    assert summary["consumed_count"] == 0
    assert summary["idle_count"] == 2
    assert summary["stop_reason"] == "max_idle_streak"


@pytest.mark.asyncio
async def test_run_stops_on_max_duration_seconds():
    worker = _FakeWorker([False, False, False, False])
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        max_iterations=50,
        max_idle_streak=50,
        max_duration_seconds=0.02,
        idle_sleep_seconds=0.02,
    )

    async def _work(_card):
        return {"ok": True}

    summary = await coordinator.run(work_fn=_work)
    assert summary["stop_reason"] == "max_duration_seconds"
    assert summary["iterations"] >= 1


@pytest.mark.asyncio
async def test_run_passes_work_fn_to_worker_each_iteration():
    worker = _FakeWorker([True, False])
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        fetch_limit=7,
        max_iterations=2,
        max_idle_streak=10,
        max_duration_seconds=60.0,
    )

    async def _work(_card):
        await asyncio.sleep(0)
        return {"ok": True}

    await coordinator.run(work_fn=_work)
    assert worker.calls == 2
    assert worker.work_fns == [_work, _work]
    assert worker.fetch_limits == [7, 7]


@pytest.mark.asyncio
async def test_run_writes_summary_artifact_when_path_provided(tmp_path):
    worker = _FakeWorker([False, False])
    coordinator = GiteaStateWorkerCoordinator(
        worker=worker,
        max_iterations=10,
        max_idle_streak=2,
        max_duration_seconds=60.0,
    )
    out_path = tmp_path / "benchmarks" / "results" / "gitea_state_worker_run.json"

    async def _work(_card):
        return {"ok": True}

    summary = await coordinator.run(work_fn=_work, summary_out=out_path)
    assert out_path.exists()
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload == summary
