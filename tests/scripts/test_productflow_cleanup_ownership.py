"""Layer: integration. ProductFlow retains acquired real engines through cleanup."""

import asyncio

import pytest

from orket.orchestration.engine import OrchestrationEngine
from scripts.productflow import productflow_support
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize("interruption", ["cancel", "timeout", "close-failure"])
async def test_productflow_retains_engine_cleanup(tmp_path, monkeypatch, record_property, interruption):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(productflow_support, "REPO_ROOT", tmp_path)
    paths = productflow_support.resolve_productflow_paths(tmp_path / "workspace")
    entered, release, owners = asyncio.Event(), asyncio.Event(), []
    original_close = OrchestrationEngine.close

    async def operate(*, paths, engine):
        owners.append(engine)
        await engine.initialize()
        assert await engine.cards.get_by_id("absent") is None
        return "observed actual SQLite"

    async def close(owner):
        if owner._closed:
            return await original_close(owner)
        entered.set()
        await asyncio.wait_for(release.wait(), 10)
        await original_close(owner)
        if interruption == "close-failure":
            await asyncio.to_thread((tmp_path / "missing-close-input").read_bytes)

    monkeypatch.setattr(OrchestrationEngine, "close", close)
    task = asyncio.create_task(productflow_support.run_productflow_operation(operate, paths=paths))
    waiter = None
    try:
        await asyncio.wait_for(entered.wait(), 10)
        if interruption == "timeout":
            waiter = asyncio.create_task(asyncio.wait_for(task, 0.02))
        else:
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        await asyncio.sleep(0.04)
        await responsive_sqlite(tmp_path / "independent.sqlite3", record_property)
        assert not task.done() and not owners[0]._closed
        release.set()
        results = await asyncio.wait_for(
            asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True), 10
        )
        assert isinstance(results[0], OSError if interruption == "close-failure" else asyncio.CancelledError)
        if waiter:
            assert isinstance(results[1], TimeoutError)
        assert len(owners) == 1 and owners[0]._closed and owners[0]._pipeline._closed
    finally:
        release.set()
        await asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True)
        for owner in owners:
            await original_close(owner)
