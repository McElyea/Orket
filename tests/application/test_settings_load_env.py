from __future__ import annotations

# Layer: unit
import asyncio
import contextlib
import os
from pathlib import Path

import pytest

import orket.settings as settings_module
from orket.exceptions import SettingsBridgeError


@contextlib.contextmanager
def _unset_pytest_marker():
    original = os.environ.pop("PYTEST_CURRENT_TEST", None)
    try:
        yield
    finally:
        if original is not None:
            os.environ["PYTEST_CURRENT_TEST"] = original


def test_load_env_parses_values_before_event_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies load_env parses real .env content, ignores comments/blanks, and preserves existing vars."""
    monkeypatch.setattr(settings_module, "_ENV_LOADED", False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\nFOO=from-file\n\nBAR=from-bar\nEXISTING=from-file\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(settings_module, "ENV_FILE", env_file)
    monkeypatch.delenv("FOO", raising=False)
    monkeypatch.delenv("BAR", raising=False)
    monkeypatch.setenv("EXISTING", "already-set")

    with _unset_pytest_marker():
        settings_module.load_env()

    assert os.environ["FOO"] == "from-file"
    assert os.environ["BAR"] == "from-bar"
    assert os.environ["EXISTING"] == "already-set"


def test_load_env_rejects_running_event_loop(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Layer: unit. Verifies load_env fails closed in async contexts instead of tripping a sync-bridge RuntimeError."""
    monkeypatch.setattr(settings_module, "_ENV_LOADED", False)
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=from-file\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "ENV_FILE", env_file)

    async def _invoke() -> None:
        settings_module.load_env()

    with _unset_pytest_marker(), pytest.raises(SettingsBridgeError, match="before the event loop starts"):
        asyncio.run(_invoke())


def test_load_env_is_noop_after_preloop_load_even_if_called_in_event_loop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Layer: unit. Verifies repeated load_env calls are no-ops after a successful pre-loop bootstrap."""
    monkeypatch.setattr(settings_module, "_ENV_LOADED", False)
    env_file = tmp_path / ".env"
    env_file.write_text("FOO=from-file\n", encoding="utf-8")
    monkeypatch.setattr(settings_module, "ENV_FILE", env_file)
    monkeypatch.delenv("FOO", raising=False)

    with _unset_pytest_marker():
        settings_module.load_env()

    async def _invoke() -> None:
        settings_module.load_env()

    with _unset_pytest_marker():
        asyncio.run(_invoke())

    assert os.environ["FOO"] == "from-file"


def test_clear_settings_cache_resets_env_loaded_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies cache clearing resets the env bootstrap guard for later test cases."""
    monkeypatch.setattr(settings_module, "_ENV_LOADED", True)

    settings_module.clear_settings_cache()

    assert settings_module._ENV_LOADED is False
