"""Layer: contract. Kernel time is explicit, immutable and normalized to UTC."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone

import pytest

from orket.core.contracts.kernel_observation import KernelObservation

pytestmark = pytest.mark.contract


@pytest.mark.parametrize("value", [None, "2030-01-01", 0, datetime(2030, 1, 1)])
def test_observation_refuses_missing_or_naive_time(value):
    with pytest.raises(ValueError, match="E_KERNEL_OBSERVATION_REQUIRES_TIMEZONE"):
        KernelObservation(value)


def test_observation_normalizes_offset_and_cannot_be_changed():
    observation = KernelObservation(datetime(2030, 1, 1, 8, tzinfo=timezone(timedelta(hours=8))))
    assert observation.observed_at == datetime(2030, 1, 1, tzinfo=UTC)
    assert observation.timestamp == "2030-01-01T00:00:00+00:00"
    with pytest.raises(FrozenInstanceError):
        observation.observed_at = datetime(2040, 1, 1, tzinfo=UTC)
