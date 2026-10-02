from __future__ import annotations

import pytest
from pydantic import ValidationError

from orket.streaming import StreamLawChecker, StreamLawViolation

pytestmark = pytest.mark.contract


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


def _commit():
    return {"authoritative": True, "commit_digest": "digest", "commit_outcome": "ok",
            "issues": [], "artifact_refs": []}


@pytest.mark.parametrize("event,diagnostic", [
    (_event(seq=1, event_type="token_delta", payload={}), "seq non-increasing"),
    ({**_event(seq=3, event_type="token_delta", payload={}), "mono_ts_ms": 0}, "mono_ts_ms decreased"),
])
def test_subscriber_rejects_out_of_order_sequence_or_clock(event, diagnostic):
    checker = StreamLawChecker()
    checker.consume(_event(seq=2, event_type="turn_accepted", payload={}))
    with pytest.raises(StreamLawViolation, match=diagnostic):
        checker.consume(event)


@pytest.mark.parametrize("terminal", ["turn_final", "turn_interrupted"])
@pytest.mark.parametrize("late", ["token_delta", "turn_final", "turn_interrupted"])
def test_terminal_turn_refuses_further_output_or_second_terminal(terminal, late):
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type=terminal, payload={}))
    with pytest.raises(StreamLawViolation, match="post-terminal event forbidden"):
        checker.consume(_event(seq=1, event_type=late, payload={}))


def test_commit_receipt_is_unique_and_requires_prior_terminal():
    checker = StreamLawChecker()
    with pytest.raises(StreamLawViolation, match="before terminal turn event"):
        checker.consume(_event(seq=0, event_type="commit_final", payload=_commit()))
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_final", payload={}))
    checker.consume(_event(seq=1, event_type="commit_final", payload=_commit()))
    with pytest.raises(StreamLawViolation, match="duplicate commit_final"):
        checker.consume(_event(seq=2, event_type="commit_final", payload=_commit()))


@pytest.mark.parametrize("missing", ["authoritative", "commit_digest", "commit_outcome", "issues", "artifact_refs"])
def test_incomplete_commit_receipt_is_refused(missing):
    payload = _commit()
    del payload[missing]
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_final", payload={}))
    with pytest.raises(StreamLawViolation, match="missing required field '" + missing + "'"):
        checker.consume(_event(seq=1, event_type="commit_final", payload=payload))


@pytest.mark.parametrize("changes,diagnostic", [
    ({"authoritative": False}, "authoritative must be true"),
    ({"authoritative": 1}, "authoritative must be true"),
    ({"commit_outcome": "completed"}, "commit_outcome invalid"),
])
def test_commit_must_declare_exact_authority_and_outcome(changes, diagnostic):
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_final", payload={}))
    with pytest.raises(StreamLawViolation, match=diagnostic):
        checker.consume(_event(seq=1, event_type="commit_final", payload={**_commit(), **changes}))


@pytest.mark.parametrize("ranges", [
    [{"start_seq": 1, "end_seq": 3}],
    [{"start_seq": "1", "end_seq": "2"}, {"start_seq": 3, "end_seq": 3}],
    [{"start_seq": False, "end_seq": False}, {"start_seq": True, "end_seq": 3}],
])
def test_declared_dropped_ranges_account_for_complete_gap(ranges):
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))
    checker.consume(_event(seq=4, event_type="turn_final", payload={"dropped_seq_ranges": ranges}))
    checker.consume(_event(seq=5, event_type="commit_final", payload={**_commit(), "commit_outcome": "fail_closed"}))


@pytest.mark.parametrize("ranges,diagnostic", [
    ([], "gap without dropped_seq_ranges"),
    ([{"start_seq": 2, "end_seq": 3}], "missing coverage for seq=1"),
    ([{"start_seq": 1, "end_seq": 1}], "incomplete coverage; first_uncovered=2"),
])
def test_declared_ranges_cannot_conceal_undisclosed_sequence_loss(ranges, diagnostic):
    checker = StreamLawChecker()
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))
    with pytest.raises(StreamLawViolation, match=diagnostic):
        checker.consume(_event(seq=4, event_type="turn_final", payload={"dropped_seq_ranges": ranges}))


@pytest.mark.parametrize("ranges", [
    [None], [{"start_seq": "bad", "end_seq": 2}], [{"start_seq": None, "end_seq": 2}],
    [{"start_seq": 2, "end_seq": 1}],
    [{"start_seq": 1, "end_seq": 2}, {"start_seq": 2, "end_seq": 3}],
])
def test_malformed_drop_ranges_fail_public_wire_admission(ranges):
    checker = StreamLawChecker()
    with pytest.raises(ValidationError):
        checker.consume(_event(seq=4, event_type="turn_final", payload={"dropped_seq_ranges": ranges}))
    checker.consume(_event(seq=0, event_type="turn_accepted", payload={}))


def test_sequence_and_terminal_state_are_isolated_by_session_and_turn():
    checker = StreamLawChecker()
    for session, turn in (("S1", "T1"), ("S1", "T2"), ("S2", "T1")):
        for seq, kind, payload in ((0, "turn_accepted", {}), (1, "turn_final", {}),
                                   (2, "commit_final", _commit())):
            checker.consume({**_event(seq=seq, event_type=kind, payload=payload),
                             "session_id": session, "turn_id": turn})
