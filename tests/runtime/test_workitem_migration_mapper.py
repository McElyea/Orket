from __future__ import annotations

from orket.runtime.migrations.workitem_mapper import map_legacy_records


def test_migration_rock_epic_issue_mapping_is_lossless() -> None:
    legacy = [
        {
            "id": "ROCK-1",
            "type": "rock",
            "status": "ready",
            "history": [{"status": "ready"}],
        },
        {
            "id": "EPIC-1",
            "type": "epic",
            "rock_id": "ROCK-1",
            "status": "in_progress",
            "audit": [{"event": "started"}],
        },
        {
            "id": "ISSUE-1",
            "type": "issue",
            "epic_id": "EPIC-1",
            "status": "done",
            "events": [{"event": "done"}],
        },
    ]

    mapped = map_legacy_records(legacy)
    by_id = {item["id"]: item for item in mapped}

    assert by_id["ROCK-1"]["kind"] == "initiative"
    assert by_id["ROCK-1"]["parent_id"] is None
    assert by_id["EPIC-1"]["kind"] == "project"
    assert by_id["EPIC-1"]["parent_id"] == "ROCK-1"
    assert by_id["ISSUE-1"]["kind"] == "task"
    assert by_id["ISSUE-1"]["parent_id"] == "EPIC-1"

    assert by_id["ROCK-1"]["id"] == "ROCK-1"
    assert by_id["EPIC-1"]["id"] == "EPIC-1"
    assert by_id["ISSUE-1"]["id"] == "ISSUE-1"

    assert by_id["ROCK-1"]["history"] == [{"status": "ready"}]
    assert by_id["EPIC-1"]["audit"] == [{"event": "started"}]
    assert by_id["ISSUE-1"]["events"] == [{"event": "done"}]
