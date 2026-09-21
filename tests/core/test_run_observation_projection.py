"""Contract: diagnostic projection preserves historical ordering, filtering and token rules."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from orket.core.contracts.run_observation_projection import handoff_edges, log_page, replay_turns, token_summary

pytestmark = pytest.mark.contract


def row(event="turn_complete", *, timestamp="2026-09-21T00:00:00+00:00", **data):
    return {"timestamp": timestamp, "event": event, "role": "Coder", "data": {
        "runtime_event": {"session_id": "OBS", "issue_id": "ISS", "turn_trace_id": "trace", **data}}}


def test_token_and_replay_model_precedence_deduplication_and_no_mutation():
    start = row("turn_start", selected_model=" Mixed:Model ")
    complete = row(selected_model="ignored", turn_index=2, tokens={"total_tokens": "7"})
    records = [start, complete, deepcopy(complete)]
    before = deepcopy(records)
    summary = token_summary(records, "OBS")
    assert summary == {
        "session_id": "OBS", "total_tokens": 7, "turn_count": 1,
        "by_role": [{"role": "coder", "tokens_total": 7}],
        "by_model": [{"model": "mixed:model", "tokens_total": 7}],
        "by_role_model": [{"role": "coder", "model": "mixed:model", "tokens_total": 7}],
        "turns": [{"turn_trace_id": "trace", "issue_id": "ISS", "turn_index": 2,
                   "role": "coder", "model": "mixed:model", "tokens_total": 7}],
    }
    assert replay_turns(records, "OBS", " CODER ") == [{
        "session_id": "OBS", "issue_id": "ISS", "turn_index": 2, "role": "coder", "turn_trace_id": "trace",
        "selected_model": "Mixed:Model", "timestamp": complete["timestamp"],
    }]
    assert replay_turns(records, "OBS", "reviewer") == []
    assert records == before


def test_token_fallback_and_distinct_replay_deduplication_contract():
    first = row(tokens=-3, turn_index="bad")
    first["data"].update(tokens="invalid", total_tokens="11", turn_index=1)
    second = deepcopy(first)
    second["data"]["turn_index"] = 2
    summary = token_summary([first, second], "OBS")
    assert summary["turn_count"] == 1 and summary["total_tokens"] == 11
    assert summary["turns"][0]["turn_index"] == 0
    assert summary["turns"][0]["model"] == "unknown"
    replay = replay_turns([first, second], "OBS", None)
    assert len(replay) == 2 and all(turn["selected_model"] is None for turn in replay)


def test_handoffs_preserve_input_order_for_ties_and_exclude_unknown_issues():
    records = [row(issue_id="A"), row(issue_id="external"), row(issue_id="B"), row(issue_id="A")]
    edges = handoff_edges(records, "OBS", {"A": 0, "B": 1})
    assert [(edge["source"], edge["target"]) for edge in edges] == [("A", "B"), ("B", "A")]
    assert all(edge["kind"] == "handoff" and edge["source_event"] == "turn_complete" for edge in edges)


def test_replay_role_filter_precedes_turn_index_conversion():
    records = [row(turn_index=float("inf"))]
    assert replay_turns(records, "OBS", "reviewer") == []
    with pytest.raises(OverflowError):
        replay_turns(records, "OBS", "coder")


def test_log_filtering_pagination_and_historical_session_fallback():
    first, second = row(), row(timestamp="2026-09-21T01:00:00+00:00")
    historical = {"timestamp": second["timestamp"], "event": "turn_complete", "role": "Coder",
                  "data": {"session_id": "OBS"}}
    records = [first, historical, second, row(timestamp="invalid")]
    page = log_page(records, session_id="OBS", event="turn_complete", role="Coder",
                    start_dt=datetime(2026, 9, 21, tzinfo=UTC), end_dt=None, limit=1, offset=1)
    assert page == {"items": [first], "count": 1, "total": 2, "limit": 1, "offset": 1}
    assert log_page(records, session_id="OBS", event=None, role="coder", start_dt=None,
                    end_dt=None, limit=20, offset=0)["total"] == 0
