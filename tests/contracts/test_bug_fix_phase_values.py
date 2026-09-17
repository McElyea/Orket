"""Bug-fix values depend only on supplied phase data and time."""
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from orket.core.domain.bug_fix_phase import BugFixPhase

pytestmark = pytest.mark.contract
START = datetime(2041, 1, 2, tzinfo=UTC)


# Layer: contract
def test_phase_creation_requires_explicit_time():
    with pytest.raises(ValidationError, match="started_at"):
        BugFixPhase(id="phase-rock", rock_id="rock")


# Layer: contract
def test_same_time_inputs_produce_identical_extension_and_expiry_values():
    first = BugFixPhase(id="phase-rock", rock_id="rock", started_at=START.isoformat())
    second = BugFixPhase.model_validate_json(first.model_dump_json())
    assert first.scheduled_end == (START + timedelta(days=7)).isoformat()
    for phase in (first, second):
        phase.extend_phase("high rate", now=START + timedelta(days=3))
        assert phase.extensions == [{"date": "2041-01-05T00:00:00+00:00", "reason": "high rate", "added_days": "7"}]
        assert not phase.is_expired(now=START + timedelta(days=13, hours=23))
        assert phase.is_expired(now=START + timedelta(days=14))
    assert first.model_dump() == second.model_dump()


# Layer: contract
def test_extension_preserves_existing_duration_cap():
    phase = BugFixPhase(id="phase-rock", rock_id="rock", started_at=START.isoformat(), max_duration_days=10)
    phase.metrics.critical_bugs = 4
    assert phase.should_extend()
    phase.extend_phase("critical bugs", now=START + timedelta(days=2))
    assert phase.current_duration_days == 10 and phase.extensions[0]["added_days"] == "3"
    assert not phase.should_extend()
