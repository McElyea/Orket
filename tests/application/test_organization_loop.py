from __future__ import annotations

from pathlib import Path

import pytest

import orket.organization_loop as organization_loop_module


@pytest.mark.asyncio
async def test_run_forever_yields_after_fast_card_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: integration. Verifies the organization loop yields after a fast card path instead of hot-spinning."""
    loop = organization_loop_module.OrganizationLoop.__new__(organization_loop_module.OrganizationLoop)
    loop.running = False
    loop.org = None
    loop.org_path = Path("model/organization.json")

    to_thread_calls: list[str] = []
    sleep_calls: list[float] = []
    executed_cards: list[str] = []

    def _fake_find() -> dict[str, str]:
        loop.running = False
        return {"id": "CARD-1", "dept": "core"}

    async def _fake_to_thread(func, *args, **kwargs):  # type: ignore[no-untyped-def]
        to_thread_calls.append(func.__name__)
        return func(*args, **kwargs)

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    class _FakePipeline:
        def __init__(self, _workspace: Path, _department: str) -> None:
            return None

        async def run_card(self, card_id: str) -> None:
            executed_cards.append(card_id)

    loop._find_next_critical_card = _fake_find
    monkeypatch.setattr(organization_loop_module.asyncio, "to_thread", _fake_to_thread)
    monkeypatch.setattr(organization_loop_module.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(organization_loop_module, "ExecutionPipeline", _FakePipeline)
    monkeypatch.setattr(organization_loop_module, "log_event", lambda *_args, **_kwargs: None)

    await organization_loop_module.OrganizationLoop.run_forever(loop)

    assert to_thread_calls == ["_fake_find"]
    assert executed_cards == ["CARD-1"]
    assert sleep_calls == [0]
