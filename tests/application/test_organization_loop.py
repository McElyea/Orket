from __future__ import annotations

from pathlib import Path

import pytest

import orket.organization_loop as organization_loop_module
from orket.application.services.runtime_construction_inputs import RuntimeConstructionInputs
from tests.helpers.runtime_result import published_result


@pytest.mark.asyncio
@pytest.mark.unit
# Layer: unit
async def test_run_forever_yields_after_fast_card_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies the organization loop yields after a fast card path instead of hot-spinning."""
    loop = organization_loop_module.OrganizationLoop.__new__(organization_loop_module.OrganizationLoop)
    loop.running = False
    loop.org = None
    loop.org_path = Path("model/organization.json")
    loop.workspace = Path("workspace/default")
    loop.construction_inputs = RuntimeConstructionInputs.capture()

    to_thread_calls: list[str] = []
    sleep_calls: list[float] = []
    executed_cards: list[str] = []

    def _fake_find() -> dict[str, str]:
        loop.running = False
        return {"id": "CARD-1", "dept": "core"}

    async def _fake_to_thread(func, *, label):
        to_thread_calls.append(func.__name__)
        return func()

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    class _FakePipeline:
        def __init__(self, _workspace: Path, _department: str, *, construction_inputs) -> None:
            return None

        async def run_card(self, card_id: str) -> None:
            executed_cards.append(card_id)
            return published_result()

        async def close(self):
            executed_cards.append("closed")

    loop._find_next_critical_card = _fake_find
    monkeypatch.setattr(organization_loop_module, "run_owned_thread", _fake_to_thread)
    monkeypatch.setattr(organization_loop_module.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(organization_loop_module, "ExecutionPipeline", _FakePipeline)
    monkeypatch.setattr(organization_loop_module, "log_event", lambda *_args, **_kwargs: None)

    await organization_loop_module.OrganizationLoop.run_forever(loop)

    assert to_thread_calls == ["_fake_find"]
    assert executed_cards == ["CARD-1", "closed"]
    assert sleep_calls == [0]
