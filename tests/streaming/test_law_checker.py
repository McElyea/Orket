from __future__ import annotations

import pytest

from orket.streaming import StreamLawChecker, StreamLawViolation


def _event(*, seq: int, event_type: str, payload: dict):
    return {
        "schema_v": "1.0",
        "session_id": "S1",
        "turn_id": "T1",
        "seq": seq,
        "mono_ts_ms": 1000 + seq,
        "event_type": event_type,
        "payload": payload,
    }


def test_law_checker_detects_duplicate_seq():
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))
    with pytest.raises(StreamLawViolation):
        checker.consume(_event(seq=0, event_type="model_selected", payload={}))


def test_law_checker_validates_commit_final_shape_and_order():
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))
    checker.consume(_event(seq=1, event_type="turn_final", payload={}))
    checker.consume(
        _event(
            seq=2,
            event_type="commit_final",
            payload={
                "authoritative": True,
                "commit_digest": "abc",
                "commit_outcome": "ok",
                "issues": [],
                "artifact_refs": [],
            },
        )
    )


def test_law_checker_rejects_gap_without_drop_ranges():
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))
    with pytest.raises(StreamLawViolation):
        checker.consume(_event(seq=2, event_type="turn_final", payload={}))
