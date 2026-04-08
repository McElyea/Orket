from __future__ import annotations

from typing import Any

import pytest

from scripts.probes import probe_support


@pytest.mark.unit
@pytest.mark.asyncio
async def test_seed_runtime_settings_context_loads_and_sets_runtime_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: dict[str, Any] = {}

    async def _fake_load_user_settings_async() -> dict[str, Any]:
        return {"state_backend_mode": "sqlite"}

    def _fake_set_runtime_settings_context(*, user_settings=None, user_preferences=None) -> None:
        observed["user_settings"] = user_settings
        observed["user_preferences"] = user_preferences

    monkeypatch.setattr("orket.settings.load_user_settings_async", _fake_load_user_settings_async)
    monkeypatch.setattr("orket.settings.set_runtime_settings_context", _fake_set_runtime_settings_context)

    await probe_support.seed_runtime_settings_context()

    assert observed == {
        "user_settings": {"state_backend_mode": "sqlite"},
        "user_preferences": None,
    }
