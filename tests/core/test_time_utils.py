from datetime import timedelta

import pytest

from orket.time_utils import configured_timezone_name, now_local


@pytest.mark.unit
def test_now_local_uses_mst_offset_when_configured(monkeypatch):
    monkeypatch.setenv("ORKET_TIMEZONE", "MST")
    ts = now_local()
    assert ts.utcoffset() == timedelta(hours=-7)
    assert configured_timezone_name() == "MST"


@pytest.mark.unit
def test_now_local_falls_back_from_invalid_timezone(monkeypatch):
    monkeypatch.setenv("ORKET_TIMEZONE", "Invalid/Zone")
    ts = now_local()
    # Fallback is UTC
    assert ts.utcoffset() == timedelta(0)

