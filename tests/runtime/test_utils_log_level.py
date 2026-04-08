from __future__ import annotations

from datetime import UTC, datetime

from orket import utils


def test_get_current_level_reads_environment_after_cache_reset(monkeypatch) -> None:
    """Layer: unit. Verifies log-level resolution is not frozen at import time."""
    monkeypatch.setenv("ORKET_LOG_LEVEL", "debug")
    utils.reset_current_level_cache()
    assert utils.get_current_level() == utils.CONSOLE_LEVELS["debug"]

    monkeypatch.setenv("ORKET_LOG_LEVEL", "error")
    utils.reset_current_level_cache()
    assert utils.get_current_level() == utils.CONSOLE_LEVELS["error"]


def test_get_eos_sprint_respects_env_base_settings(monkeypatch) -> None:
    """Layer: unit. Verifies EOS sprint calculation can be shifted through the configured base date and sprint marker."""
    monkeypatch.setenv("ORKET_EOS_SPRINT_BASE_DATE", "2026-01-05")
    monkeypatch.setenv("ORKET_EOS_SPRINT_BASE_QUARTER", "2")
    monkeypatch.setenv("ORKET_EOS_SPRINT_BASE_SPRINT", "3")
    utils._eos_sprint_base_settings.cache_clear()

    sprint = utils.get_eos_sprint(datetime(2026, 1, 12, tzinfo=UTC))

    assert sprint == "Q2 S4"
