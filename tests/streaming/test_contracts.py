from __future__ import annotations

import pytest

from orket.streaming.contracts import StreamEvent, StreamEventType


def test_stream_event_requires_valid_type():
    with pytest.raises(Exception):
        StreamEvent(
            session_id="s1",
            turn_id="t1",
            seq=0,
            mono_ts_ms=1,
            event_type="bad_type",
            payload={},
        )


def test_stream_event_validates_drop_ranges():
    with pytest.raises(ValueError):
        StreamEvent(
            session_id="s1",
            turn_id="t1",
            seq=3,
            mono_ts_ms=1,
            event_type=StreamEventType.TURN_FINAL,
            payload={
                "dropped_seq_ranges": [
                    {"start_seq": 5, "end_seq": 7},
                    {"start_seq": 7, "end_seq": 9},
                ]
            },
        )
