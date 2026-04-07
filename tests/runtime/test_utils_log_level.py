from __future__ import annotations

from orket import utils


def test_get_current_level_reads_environment_after_cache_reset(monkeypatch) -> None:
    """Layer: unit. Verifies log-level resolution is not frozen at import time."""
    monkeypatch.setenv("ORKET_LOG_LEVEL", "debug")
    utils.reset_current_level_cache()
    assert utils.get_current_level() == utils.CONSOLE_LEVELS["debug"]

    monkeypatch.setenv("ORKET_LOG_LEVEL", "error")
    utils.reset_current_level_cache()
    assert utils.get_current_level() == utils.CONSOLE_LEVELS["error"]
