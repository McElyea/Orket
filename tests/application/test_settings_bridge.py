# Layer: unit

from __future__ import annotations

import pytest

from orket.exceptions import SettingsBridgeError
from orket.settings import _run_settings_sync


async def _noop_settings() -> dict[str, str]:
    return {}


async def test_run_settings_sync_raises_typed_error_inside_event_loop() -> None:
    with pytest.raises(SettingsBridgeError, match="load_user_settings must run before the event loop starts"):
        _run_settings_sync(_noop_settings(), operation="load_user_settings")
