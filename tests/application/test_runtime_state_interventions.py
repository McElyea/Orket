from __future__ import annotations

import pytest

from orket.state import GlobalState


@pytest.mark.asyncio
async def test_interventions_roundtrip_and_copy_semantics() -> None:
    state = GlobalState()
    payload = {"reason": "manual_override", "actor": "operator"}
    await state.set_intervention("session-1", payload)

    fetched = await state.get_intervention("session-1")
    assert fetched == payload
    assert fetched is not payload

    fetched["reason"] = "mutated"
    fetched_again = await state.get_intervention("session-1")
    assert fetched_again == payload

    snapshot = await state.get_interventions()
    assert snapshot == {"session-1": payload}
    snapshot["session-1"]["reason"] = "mutated-again"
    assert await state.get_intervention("session-1") == payload

    await state.remove_intervention("session-1")
    assert await state.get_intervention("session-1") is None
