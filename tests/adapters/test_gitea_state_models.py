import json

import pytest

from orket.adapters.storage.gitea_state_models import (
    CardSnapshot,
    EVENT_MARKER,
    SNAPSHOT_MARKER,
    build_event_comment,
    decode_snapshot,
    encode_snapshot,
    parse_event_comment,
)


def test_encode_decode_snapshot_round_trip():
    snapshot = CardSnapshot(
        card_id="ISSUE-42",
        state="ready",
        version=7,
        metadata={"priority": "high"},
    )
    body = encode_snapshot(snapshot)
    assert body.startswith(SNAPSHOT_MARKER)

    restored = decode_snapshot(body)
    assert restored.card_id == "ISSUE-42"
    assert restored.state == "ready"
    assert restored.version == 7
    assert restored.metadata["priority"] == "high"


def test_decode_snapshot_rejects_missing_marker():
    with pytest.raises(ValueError, match="Missing ORKET snapshot marker"):
        decode_snapshot("plain issue description")


def test_event_comment_round_trip_with_idempotency_key():
    comment = build_event_comment(
        "transition",
        {"from": "ready", "to": "in_progress"},
        idempotency_key="evt-1",
        created_at="2026-02-15T10:00:00+00:00",
    )
    assert comment.startswith(EVENT_MARKER)

    parsed = parse_event_comment(comment)
    assert parsed.event_type == "transition"
    assert parsed.payload == {"from": "ready", "to": "in_progress"}
    assert parsed.idempotency_key == "evt-1"


def test_event_comment_is_compact_json_payload():
    comment = build_event_comment("guard_failure", {"rule_id": "HALLUCINATION.FILE_NOT_FOUND"})
    payload = comment.split(" ", 1)[1]
    parsed = json.loads(payload)
    assert parsed["event_type"] == "guard_failure"
    assert parsed["payload"]["rule_id"] == "HALLUCINATION.FILE_NOT_FOUND"
