from __future__ import annotations

import argparse
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
