"""Layer: integration. Governance scopes retain actual engine cleanup on interruption."""

import asyncio

import pytest

from orket.exceptions import CardNotFound
from orket.orchestration.engine import OrchestrationEngine
from scripts.governance import record_truthful_runtime_artifact_provenance_live_proof as provenance
from scripts.governance import record_truthful_runtime_packet1_live_proof as packet1
from scripts.governance import record_truthful_runtime_packet2_repair_live_proof as packet2
from tests.helpers.kernel_state_probe import responsive_sqlite

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest.mark.parametrize("command", [packet1, packet2, provenance])
@pytest.mark.parametrize("interruption", ["cancel", "timeout", "close-failure"])
async def test_governance_scope_retains_cleanup(tmp_path, monkeypatch, record_property, command, interruption):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORKET_DURABLE_ROOT", str(tmp_path / "durable"))
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    entered, release, owners = asyncio.Event(), asyncio.Event(), []
    original_close = OrchestrationEngine.close

    async def close(owner):
        if owner._closed:
            return await original_close(owner)
        owners.append(owner)
        await owner.initialize()
        assert await owner.cards.get_by_id("absent") is None
        entered.set()
        await asyncio.wait_for(release.wait(), 10)
        await original_close(owner)
        if interruption == "close-failure":
            await asyncio.to_thread((tmp_path / "missing-close-input").read_bytes)

    monkeypatch.setattr(OrchestrationEngine, "close", close)
    options = {"repair_injection_applied": {"value": False}} if command is packet2 else {}
    task = asyncio.create_task(
        command._execute_live_proof(
            workspace=tmp_path / "workspace",
            config_root=tmp_path,
            db_path=str(tmp_path / "runtime.db"),
            model="unadmitted-fixture",
            provider="openai_compat",
            epic_id="absent",
            **options,
        )
    )
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
        # The original operation refusal survives cancellation during retained cleanup.
        assert isinstance(results[0], OSError if interruption == "close-failure" else CardNotFound)
        if waiter:
            assert isinstance(results[1], CardNotFound)
            assert str(results[1]) == "Card absent not found."
        assert len(owners) == 1 and owners[0]._closed and owners[0]._pipeline._closed
    finally:
        release.set()
        await asyncio.gather(task, *([waiter] if waiter else []), return_exceptions=True)
        for owner in owners:
            await original_close(owner)
