"""Layer: integration. Public orchestration retains actual HTTP and fixture observations."""

import asyncio
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.runtime_policy_inputs import ArchitecturePolicySnapshot
from orket.application.workflows.orchestrator import Orchestrator
from orket.core.domain.sandbox import SandboxStatus
from tests.helpers.observed_http_server import observed_http_server
from tests.helpers.turn_artifacts import artifact_test_utc_now

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def prepare(root, url):
    def fixture():
        directory = root / "verification"
        directory.mkdir()
        (directory / "fixture.py").write_text("def verify(data): return 0\n", encoding="utf-8")

    await asyncio.to_thread(fixture)
    cards = AsyncCardRepository(root / "cards.db")
    await cards.save({"id": "HTTP", "summary": "Observed verification", "seat": "developer", "build_id": "BUILD",
        "verification": {"fixture_path": "verification/fixture.py", "scenarios": [
            {"id": "http", "description": "Falsy comparison", "input_data": {"endpoint": "/probe"}, "expected_output": 0}]}})
    sandbox = SimpleNamespace(id="sandbox-BUILD", status=SandboxStatus.RUNNING, api_url=url)
    owner = SimpleNamespace(registry={"sandbox-BUILD": sandbox})
    return Orchestrator(root, cards, None, None, root, str(root / "cards.db"), None, owner, architecture_policy=ArchitecturePolicySnapshot(False), turn_clock=artifact_test_utc_now), cards


@pytest.mark.parametrize("actual,counts", [(0, (2, 0)), ({"unexpected": True}, (1, 1))], ids=["matching", "mismatch"])
async def test_public_http_and_fixture_observations_are_persisted(tmp_path, monkeypatch, actual, counts):
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")

    async def respond(_request):
        return 200, actual

    async with observed_http_server(respond) as (url, requests):
        orchestrator, cards = await prepare(tmp_path, url)
        result = await orchestrator.verify_issue("HTTP")
        retained = (await cards.get_by_id("HTTP")).model_dump()["verification"]
        assert len(requests) == 1
        assert (result.total_scenarios, result.passed, result.failed) == (2, *counts)
        assert result.process_lifetime["cleanup_confirmed"]
        assert retained["last_run"] == result.model_dump()
        assert retained["scenarios"][0]["actual_output"] == actual
        assert retained["scenarios"][0]["status"] == ("pass" if counts[1] == 0 else "fail")


async def test_public_cancelled_http_does_not_persist_fixture_or_http_results(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    entered, release = asyncio.Event(), asyncio.Event()

    async def respond(_request):
        entered.set()
        await asyncio.wait_for(release.wait(), timeout=5)
        return 200, 0

    async with observed_http_server(respond, allow_disconnect=True) as (url, requests):
        orchestrator, cards = await prepare(tmp_path, url)
        before = (await cards.get_by_id("HTTP")).model_dump()
        task = asyncio.create_task(orchestrator.verify_issue("HTTP"))
        try:
            await asyncio.wait_for(entered.wait(), timeout=5)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, timeout=2)
        finally:
            release.set()
            await asyncio.wait_for(asyncio.gather(task, return_exceptions=True), timeout=5)
        assert len(requests) == 1
        assert (await cards.get_by_id("HTTP")).model_dump() == before
