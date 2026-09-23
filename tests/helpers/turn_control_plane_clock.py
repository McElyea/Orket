"""Ordered time for turns and enclosing issue dispatch; reversal has separate cases."""
from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace

import pytest

from orket.application.services import turn_tool_control_plane_closeout as closeout
from orket.application.services import turn_tool_control_plane_reconciliation as reconciliation
from orket.application.services import turn_tool_control_plane_recovery as recovery
from orket.application.services import turn_tool_control_plane_service as service
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.application.workflows import orchestrator
from tests.helpers import turn_artifacts


@pytest.fixture
def deterministic_turn_clock(monkeypatch):
    ticks = count()
    origin = datetime(2026, 1, 1, tzinfo=UTC)

    def utc_now():
        return (origin + timedelta(microseconds=next(ticks))).isoformat()

    for module in (service, closeout, recovery, reconciliation):
        monkeypatch.setattr(module, 'utc_now', utc_now)
    monkeypatch.setattr(orchestrator, 'utc_now_iso', utc_now)
    # Pipeline composition explicitly supplies this clock to enclosing issue dispatch.
    monkeypatch.setattr(RuntimeInputService, 'utc_now', lambda self: datetime.fromisoformat(utc_now()))
    # Direct turn fixtures explicitly supply the same ordered observation source.
    monkeypatch.setattr(turn_artifacts, 'datetime', SimpleNamespace(now=lambda zone: datetime.fromisoformat(utc_now())))
    return utc_now
