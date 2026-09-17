"""Layer: contract. EOS results depend only on explicit baseline and time values."""
from datetime import UTC, datetime, timedelta, timezone

import pytest

from orket.core.contracts.eos_calendar import EosSprintBaseline

pytestmark = pytest.mark.contract


@pytest.mark.parametrize(('settings', 'now', 'expected'), [
    ({}, datetime(2026, 2, 2, tzinfo=UTC), 'Q1 S6'),
    ({}, datetime(2026, 2, 11, tzinfo=UTC), 'Q1 S7'),
    ({}, datetime(2026, 1, 26, tzinfo=UTC), 'Q1 S5'),
    ({'ORKET_EOS_SPRINT_BASE_QUARTER': '3', 'ORKET_EOS_SPRINT_BASE_SPRINT': '13'},
     datetime(2026, 2, 9, tzinfo=UTC), 'Q4 S1'),
    ({'ORKET_EOS_SPRINT_BASE_DATE': 'invalid', 'ORKET_EOS_SPRINT_BASE_QUARTER': '9'},
     datetime(2026, 2, 9, tzinfo=UTC), 'Q1 S7'),
    ({'ORKET_EOS_SPRINT_BASE_QUARTER': 'bad', 'ORKET_EOS_SPRINT_BASE_SPRINT': ''},
     datetime(2026, 2, 9, tzinfo=UTC), 'Q1 S7'),
    ({'ORKET_EOS_SPRINT_BASE_DATE': '2026-02-02T07:00:00+00:00'},
     datetime(2026, 2, 9, tzinfo=timezone(timedelta(hours=-7))), 'Q1 S7'),
])
def test_eos_sprint_explicit_baseline(settings, now, expected):
    baseline = EosSprintBaseline.from_environment(settings)
    settings['ORKET_EOS_SPRINT_BASE_QUARTER'] = '100'
    assert baseline.current_sprint(now) == expected
