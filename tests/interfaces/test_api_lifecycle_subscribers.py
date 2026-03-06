from __future__ import annotations

import pytest

from orket.interfaces import api as api_module
from orket.logging import event_subscriber_count
from orket.logging import subscribe_to_events
from orket.logging import unsubscribe_from_events


@pytest.mark.asyncio
async def test_api_lifespan_subscriber_count_stable_across_repeated_cycles() -> None:
    baseline = event_subscriber_count()
    for _ in range(5):
        async with api_module.lifespan(api_module.app):
            assert event_subscriber_count() == baseline + 1
        assert event_subscriber_count() == baseline


def test_subscribe_to_events_is_idempotent_for_same_callback_identity() -> None:
    baseline = event_subscriber_count()

    def _callback(_record: dict) -> None:
        return None

    subscribe_to_events(_callback)
    subscribe_to_events(_callback)
    assert event_subscriber_count() == baseline + 1

    unsubscribe_from_events(_callback)
    assert event_subscriber_count() == baseline
