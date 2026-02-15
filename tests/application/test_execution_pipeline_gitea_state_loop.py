from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.runtime.execution_pipeline import ExecutionPipeline


@pytest.mark.asyncio
async def test_run_gitea_state_loop_requires_gitea_mode():
    pipeline = object.__new__(ExecutionPipeline)
    pipeline.state_backend_mode = "local"

    with pytest.raises(ValueError, match="state_backend_mode='gitea'"):
        await pipeline.run_gitea_state_loop(worker_id="worker-1")


@pytest.mark.asyncio
async def test_run_gitea_state_loop_wires_adapter_worker_and_coordinator(monkeypatch, tmp_path):
    pipeline = object.__new__(ExecutionPipeline)
    pipeline.state_backend_mode = "gitea"
    pipeline.org = SimpleNamespace(process_rules={})
    called_cards = []

    async def _run_card(card_id: str, **_kwargs):
        called_cards.append(card_id)
        return {"ok": True}

    pipeline.run_card = _run_card

    import orket.runtime.execution_pipeline as module

    monkeypatch.setattr(
        module,
        "collect_gitea_state_pilot_inputs",
        lambda: {
            "state_backend_mode": "gitea",
            "pilot_enabled": True,
            "gitea_url": "https://gitea.local",
            "gitea_token": "token",
            "gitea_owner": "acme",
            "gitea_repo": "orket",
        },
    )
    monkeypatch.setattr(module, "evaluate_gitea_state_pilot_readiness", lambda _inputs: {"ready": True})
    monkeypatch.setattr(module, "load_user_settings", lambda: {})

    seen = {}

    class _FakeAdapter:
        def __init__(self, **kwargs):
            seen["adapter"] = kwargs

    class _FakeWorker:
        def __init__(self, **kwargs):
            seen["worker"] = kwargs

    class _FakeCoordinator:
        def __init__(self, **kwargs):
            seen["coordinator"] = kwargs

        async def run(self, *, work_fn, summary_out=None):
            await work_fn({"card_id": "ISSUE-77"})
            summary = {
                "iterations": 1,
                "consumed_count": 1,
                "idle_count": 0,
                "stop_reason": "max_iterations",
                "elapsed_ms": 5,
            }
            if summary_out is not None:
                out = Path(summary_out)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            return summary

    monkeypatch.setattr(module, "GiteaStateAdapter", _FakeAdapter)
    monkeypatch.setattr(module, "GiteaStateWorker", _FakeWorker)
    monkeypatch.setattr(module, "GiteaStateWorkerCoordinator", _FakeCoordinator)

    summary_path = tmp_path / "benchmarks" / "results" / "run_summary.json"
    payload = await pipeline.run_gitea_state_loop(
        worker_id="worker-1",
        fetch_limit=9,
        max_iterations=2,
        max_idle_streak=2,
        max_duration_seconds=30.0,
        summary_out=summary_path,
    )

    assert called_cards == ["ISSUE-77"]
    assert seen["adapter"]["base_url"] == "https://gitea.local"
    assert seen["worker"]["worker_id"] == "worker-1"
    assert seen["coordinator"]["fetch_limit"] == 9
    assert payload["summary"]["consumed_count"] == 1
    assert summary_path.exists()
