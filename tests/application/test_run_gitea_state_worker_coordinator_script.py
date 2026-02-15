from __future__ import annotations

import argparse
import asyncio
import json

from scripts import run_gitea_state_worker_coordinator as script


def _args(**overrides) -> argparse.Namespace:
    base = {
        "worker_id": "",
        "fetch_limit": 5,
        "lease_seconds": 30,
        "renew_interval_seconds": 5.0,
        "max_iterations": 100,
        "max_idle_streak": 10,
        "max_duration_seconds": 60.0,
        "idle_sleep_seconds": 0.0,
        "summary_out": "benchmarks/results/gitea_state_worker_run_summary.json",
        "allow_mutate": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_main_requires_allow_mutate(monkeypatch) -> None:
    monkeypatch.setattr(script, "_parse_args", lambda: _args(allow_mutate=False))
    assert script.main() == 2


def test_main_writes_summary_payload(monkeypatch, tmp_path) -> None:
    out_path = tmp_path / "gitea_state_worker_run_summary.json"
    monkeypatch.setattr(script, "_parse_args", lambda: _args(allow_mutate=True, summary_out=str(out_path)))

    async def _fake_run_loop(_args):
        return {"timestamp_utc": "2026-02-15T00:00:00+00:00", "worker_id": "w-1", "summary": {"iterations": 1}}

    monkeypatch.setattr(script, "_run_loop", _fake_run_loop)
    assert script.main() == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["worker_id"] == "w-1"
    assert payload["summary"]["iterations"] == 1


def test_main_returns_failure_on_loop_exception(monkeypatch) -> None:
    monkeypatch.setattr(script, "_parse_args", lambda: _args(allow_mutate=True))

    async def _boom(_args):
        raise RuntimeError("bad")

    monkeypatch.setattr(script, "_run_loop", _boom)
    assert script.main() == 1


def test_run_loop_uses_policy_env_defaults_for_bounds(monkeypatch) -> None:
    args = _args(
        allow_mutate=True,
        max_iterations=None,
        max_idle_streak=None,
        max_duration_seconds=None,
    )
    monkeypatch.setenv("ORKET_GITEA_WORKER_MAX_ITERATIONS", "33")
    monkeypatch.setenv("ORKET_GITEA_WORKER_MAX_IDLE_STREAK", "4")
    monkeypatch.setenv("ORKET_GITEA_WORKER_MAX_DURATION_SECONDS", "90")
    monkeypatch.setattr(script, "collect_gitea_state_pilot_inputs", lambda: {})
    monkeypatch.setattr(script, "evaluate_gitea_state_pilot_readiness", lambda _inputs: {"ready": True})
    monkeypatch.setattr(script, "_required_env", lambda _name: "x")
    monkeypatch.setattr(script, "_resolve_worker_id", lambda _raw: "worker-1")

    seen = {}

    class _FakeAdapter:
        def __init__(self, **_kwargs):
            pass

    class _FakeWorker:
        def __init__(self, **_kwargs):
            pass

    class _FakeCoordinator:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def run(self, *, work_fn):
            return {"iterations": 0, "consumed_count": 0, "idle_count": 0, "stop_reason": "max_idle_streak", "elapsed_ms": 0}

    monkeypatch.setattr(script, "GiteaStateAdapter", _FakeAdapter)
    monkeypatch.setattr(script, "GiteaStateWorker", _FakeWorker)
    monkeypatch.setattr(script, "GiteaStateWorkerCoordinator", _FakeCoordinator)

    payload = asyncio.run(script._run_loop(args))
    assert payload["max_iterations"] == 33
    assert payload["max_idle_streak"] == 4
    assert payload["max_duration_seconds"] == 90.0
    assert seen["max_iterations"] == 33
    assert seen["max_idle_streak"] == 4
    assert seen["max_duration_seconds"] == 90.0
