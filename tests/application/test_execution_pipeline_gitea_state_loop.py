from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.application.services.runtime_input_service import RuntimeInputService
from orket.runtime.execution_pipeline import ExecutionPipeline
from tests.helpers.runtime_result import published_result

pytestmark = pytest.mark.contract


def _pipeline(tmp_path, mode):
    pipeline = object.__new__(ExecutionPipeline)
    pipeline._initialized = True
    pipeline.state_backend_mode = mode
    pipeline.org = SimpleNamespace(process_rules={})
    pipeline.runtime_inputs = RuntimeInputService()
    pipeline.runtime_context = SimpleNamespace(construction_inputs=None)
    pipeline.orchestrator = SimpleNamespace(
        control_plane_execution_repository=SimpleNamespace(db_path=tmp_path / 'control_plane.sqlite3'))
    return pipeline


@pytest.mark.asyncio
async def test_run_gitea_state_loop_requires_gitea_mode(tmp_path):
    pipeline = _pipeline(tmp_path, "local")

    with pytest.raises(ValueError, match="state_backend_mode='gitea'"):
        await pipeline.run_gitea_state_loop(worker_id="worker-1")


@pytest.mark.asyncio
# Layer: contract
async def test_run_gitea_state_loop_wires_adapter_worker_and_coordinator(monkeypatch, tmp_path):
    """Layer: contract. Verifies selected ports and canonical card dispatch through controlled collaborators."""
    pipeline = _pipeline(tmp_path, "gitea")
    called_cards = []

    async def _run_card(card_id: str, **_kwargs):
        called_cards.append(card_id)
        return published_result()

    pipeline.run_card = _run_card

    import orket.runtime.gitea_state_loop as module

    monkeypatch.setattr(
        module,
        "collect_gitea_state_pilot_inputs",
        lambda *, environment: {
            "state_backend_mode": "gitea",
            "pilot_enabled": True,
            "gitea_url": "https://gitea.local",
            "gitea_token": "token",
            "gitea_owner": "acme",
            "gitea_repo": "orket",
        },
    )
    monkeypatch.setattr(module, "evaluate_gitea_state_pilot_readiness", lambda _inputs: {"ready": True})
    async def _load_user_settings():
        return {}

    monkeypatch.setattr(module, "load_user_settings_async", _load_user_settings)

    seen = {}

    class _FakeAdapter:
        def __init__(self, **kwargs):
            seen["adapter"] = kwargs

        async def close(self):
            seen["closed"] = True

    class _FakeWorker:
        def __init__(self, **kwargs):
            seen["worker"] = kwargs

    class _FakeCoordinator:
        def __init__(self, **kwargs):
            seen["coordinator"] = kwargs

        async def run(self, *, work_fn, summary_out=None):
            await work_fn({"card_id": "ISSUE-77", "issue_number": 77})
            summary = {
                "iterations": 1,
                "consumed_count": 1,
                "idle_count": 0,
                "stop_reason": "max_iterations",
                "elapsed_ms": 5,
            }
            if summary_out is not None:
                out = Path(summary_out)
                await asyncio.to_thread(out.parent.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread(out.write_text, json.dumps(summary, indent=2), encoding="utf-8")
            return summary

    monkeypatch.setattr(module, "create_gitea_state_adapter", _FakeAdapter)
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
    assert seen["worker"]["control_plane_checkpoint_service"] is not None
    assert seen["worker"]["control_plane_execution_service"] is not None
    assert seen["worker"]["control_plane_lease_service"] is not None
    assert seen["worker"]["control_plane_reservation_service"] is not None
    assert seen["coordinator"]["fetch_limit"] == 9
    assert seen["coordinator"]["runtime_inputs"] is pipeline.runtime_inputs
    assert seen["worker"]["control_plane_execution_service"].now_utc == pipeline.runtime_inputs.utc_now_iso
    assert seen["closed"] is True
    assert payload["summary"]["consumed_count"] == 1
    assert await asyncio.to_thread(summary_path.exists)
