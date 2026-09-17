"""Real SQLite and public fixture execution, cancellation, and retained observations."""
from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.adapters.storage.async_card_repository import AsyncCardRepository
from orket.application.services.command_process_supervisor import CommandProcessCancelled
from orket.application.workflows.orchestrator import Orchestrator
from tests.integration.test_verification_process_lifetime import (
    assert_stopped,
    await_tree,
    observe_processes,
    stop_observed,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]
WORKER = Path(__file__).parents[1] / "integration/verification_lifetime_worker.py"


def prepare_fixture(root, source=None):
    directory = root / "verification"
    directory.mkdir(parents=True)
    if source is None:
        source = WORKER.read_text(encoding="utf-8")
        source += ('\ndef verify(data):\n'
                   '    sys.argv = [__file__, data["root"], "2", *data["flags"]]\n'
                   '    main()\n    return 1\n')
    (directory / "fixture.py").write_text(source, encoding="utf-8")


async def prepare_orchestrator(root, flags=(), source=None):
    await asyncio.to_thread(prepare_fixture, root, source)
    cards = AsyncCardRepository(root / "cards.db")
    await cards.save({"id": "FIXTURE", "summary": "Fixture lifetime", "seat": "developer",
        "verification": {"fixture_path": "verification/fixture.py", "scenarios": [
            {"id": "one", "description": "real fixture", "input_data": {"root": str(root), "flags": list(flags)},
             "expected_output": 1}]}})
    sandbox = SimpleNamespace(registry={})
    orchestrator = Orchestrator(root, cards, None, None, root, str(root / "cards.db"), None, sandbox)
    return orchestrator, cards


@pytest.mark.parametrize("stop", ["cancel", "repeated-cancel", "timeout"])
@pytest.mark.parametrize("flags", [[], ["detached", "ignore-term"]], ids=["ordinary", "detached-resistant"])
# Layer: integration
async def test_public_fixture_lifetime(tmp_path, monkeypatch, stop, flags):
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    monkeypatch.setenv("ORKET_VERIFY_TIMEOUT_SEC", "1.5" if stop == "timeout" else "15")
    orchestrator, cards = await prepare_orchestrator(tmp_path, flags)
    before = (await cards.get_by_id("FIXTURE")).model_dump()["verification"]
    task = asyncio.create_task(orchestrator.verify_issue("FIXTURE"))
    processes = []
    try:
        processes = await await_tree(tmp_path)
        if stop == "timeout":
            result = await asyncio.wait_for(asyncio.shield(task), 7)
            assert result.failed == 1 and result.process_lifetime["reason"] == "timeout"
            retained = (await cards.get_by_id("FIXTURE")).model_dump()["verification"]["last_run"]
            assert retained["process_lifetime"] == result.process_lifetime
        else:
            task.cancel()
            if stop == "repeated-cancel":
                for _ in range(20):
                    if task.done():
                        break
                    await asyncio.sleep(0.01)
                    task.cancel()
            with pytest.raises(CommandProcessCancelled) as cancelled:
                await asyncio.wait_for(task, 7)
            assert cancelled.value.lifetime.cleanup_confirmed
            assert (await cards.get_by_id("FIXTURE")).model_dump()["verification"] == before
        await assert_stopped(processes, tmp_path)
    finally:
        if not processes:
            processes = await asyncio.to_thread(observe_processes, tmp_path)
        await asyncio.to_thread(stop_observed, processes)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


# Layer: integration
async def test_public_fixture_result_is_retained(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    orchestrator, cards = await prepare_orchestrator(tmp_path, source="def verify(data): return 1\n")
    result = await orchestrator.verify_issue("FIXTURE")
    retained = (await cards.get_by_id("FIXTURE")).model_dump()["verification"]
    assert result.passed == 1 and result.process_lifetime["cleanup_confirmed"]
    assert retained["last_run"]["process_lifetime"] == result.process_lifetime
    assert retained["scenarios"][0]["status"] == "pass"


# Layer: integration
async def test_parallel_public_fixture_calls_leave_loop_responsive(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_VERIFY_EXECUTION_MODE", "subprocess")
    source = ("import time\nfrom pathlib import Path\ndef verify(data):\n"
              "    Path(data['root'], 'started').touch()\n    time.sleep(0.5)\n    return 1\n")
    first, _ = await prepare_orchestrator(tmp_path / "first", source=source)
    second, _ = await prepare_orchestrator(tmp_path / "second", source=source)
    tasks = [asyncio.create_task(item.verify_issue("FIXTURE")) for item in (first, second)]
    try:
        for _ in range(200):
            if await asyncio.to_thread(lambda: all((tmp_path / name / "started").exists() for name in ("first", "second"))):
                break
            await asyncio.sleep(0.01)
        assert not any(task.done() for task in tasks)
        ticks = 0
        while not any(task.done() for task in tasks):
            await asyncio.sleep(0.01)
            ticks += 1
        assert ticks >= 5
        assert all(result.passed == 1 for result in await asyncio.gather(*tasks))
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
