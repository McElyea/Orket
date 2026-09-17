"""Explicit UTC input for Gitea controls; reversal and live UTC have separate proof."""
from datetime import UTC, datetime, timedelta
from itertools import count


def ordered_utc_clock():
    ticks = count()

    def now():
        return (datetime(2026, 3, 24, 1, 0, 1, tzinfo=UTC) + timedelta(milliseconds=next(ticks))).isoformat()

    return now
