from __future__ import annotations

import pytest

import orket.state as state_module
from orket.state import GlobalState, reset_runtime_state


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


@pytest.mark.asyncio
async def test_fresh_runtime_state_fixture_replaces_runtime_state(fresh_runtime_state) -> None:
    """Layer: unit. Verifies tests can isolate the module-level runtime_state singleton."""
    assert state_module.runtime_state is fresh_runtime_state

    await state_module.runtime_state.set_intervention("session-1", {"reason": "isolated"})

    assert await fresh_runtime_state.get_intervention("session-1") == {"reason": "isolated"}


def test_reset_runtime_state_replaces_module_singleton() -> None:
    """Layer: unit. Verifies the runtime-state reset helper swaps the module-level singleton through the factory seam."""
    original = state_module.runtime_state

    reset = reset_runtime_state()

    assert state_module.runtime_state is reset
    assert state_module.runtime_state is not original


@pytest.mark.asyncio
async def test_interaction_session_registry_roundtrip() -> None:
    """Layer: unit. Verifies GlobalState tracks interaction-session surface presence separately from task state."""
    state = GlobalState()

    assert await state.is_interaction_session("session-1") is False

    await state.register_interaction_session("session-1")
    assert await state.is_interaction_session("session-1") is True

    await state.unregister_interaction_session("session-1")
    assert await state.is_interaction_session("session-1") is False
