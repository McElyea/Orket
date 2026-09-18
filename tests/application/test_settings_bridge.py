# Layer: unit

from __future__ import annotations

import pytest

import orket.settings as settings_module
from orket.exceptions import SettingsBridgeError
from orket.settings import _run_settings_sync


async def _noop_settings() -> dict[str, str]:
    return {}


async def test_run_settings_sync_raises_typed_error_inside_event_loop() -> None:
    with pytest.raises(SettingsBridgeError, match="load_user_settings must run before the event loop starts"):
        _run_settings_sync(_noop_settings(), operation="load_user_settings")


def test_run_settings_sync_preserves_bound_runtime_context() -> None:
    """Layer: unit. asyncio.run propagates the caller's captured context into its coroutine."""
    async def read_snapshot():
        return settings_module.load_user_settings()

    settings_module.set_runtime_settings_context(user_settings={"state_backend_mode": "sqlite"})
    try:
        assert _run_settings_sync(read_snapshot(), operation="load_user_settings") == {"state_backend_mode": "sqlite"}
    finally:
        settings_module.clear_runtime_settings_context()
