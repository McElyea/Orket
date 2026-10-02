"""Pure retention-plan contract; recommendations here never delete files."""
from copy import deepcopy
from datetime import UTC, datetime

import pytest

from orket.runtime.policy.retention_policy import (
    RetentionPolicy,
    build_retention_plan,
    check_id,
    smoke_profile,
)

pytestmark = pytest.mark.contract
NOW = datetime(2026, 9, 21, tzinfo=UTC)


@pytest.mark.parametrize("path,expected", [
    ("checks/day/alpha_fail.json", "alpha"), ("checks/day/_fail.json", "_fail"),
    ("checks/day/_pass.json", "_pass"), ("checks/day/plain.json", "plain"),
    ("notes/report.json", "report"), ("", "_unknown"), ("checks/day/", "_unknown"),
])
def test_check_identity_keeps_empty_prefix_and_nonstandard_names_unambiguous(path, expected):
    assert check_id(path) == expected


@pytest.mark.parametrize("path,profile", [("smoke//case.json", "_unknown"), ("other/a", "_unknown")])
def test_smoke_profile_falls_back_for_missing_namespace_or_identity(path, profile):
    assert smoke_profile(path) == profile


@pytest.mark.parametrize("timestamp,size", [("", "bad"), ("invalid", {}), ("1970-01-01", -1)])
def test_malformed_entry_metadata_is_deterministic_without_input_repair(timestamp, size):
    entries = [{"path": " "}, {"path": r"\notes\old.json", "updated_at": timestamp, "size_bytes": size}]
    before = deepcopy(entries)
    plan = build_retention_plan(entries, as_of=NOW)
    assert plan["summary"] == {"total_count": 1, "keep_count": 1, "delete_count": 0, "delete_bytes": 0}
    assert plan["actions"] == [{"path": "notes/old.json", "namespace": "other", "action": "keep",
        "reason": "default_keep", "pinned": False, "size_bytes": 0,
        "updated_at": "1970-01-01T00:00:00+00:00", "status": "unknown"}]
    assert entries == before


def test_pinned_and_recent_entries_survive_ttl_and_cap_planning():
    entries = [
        {"path": "smoke/p/pinned", "updated_at": "2000-01-01", "pinned": True},
        {"path": "smoke/p/newest", "updated_at": "2026-09-21"},
        {"path": "smoke/p/recent", "updated_at": "2026-09-20"},
        {"path": "checks/old/pinned_fail.json", "updated_at": "2000-01-01", "pinned": True},
        {"path": "checks/today/recent.json", "updated_at": "2026-09-20"},
        {"path": "artifacts/pinned", "updated_at": "2000-01-01", "pinned": True, "size_bytes": 100},
        {"path": "artifacts/recent", "updated_at": "2026-09-20", "size_bytes": 1},
    ]
    before = deepcopy(entries)
    plan = build_retention_plan(entries, as_of=NOW,
        policy=RetentionPolicy(smoke_keep_latest_per_profile=1, artifacts_size_cap_bytes=1))
    actions = {row["path"]: row for row in plan["actions"]}
    assert {path for path, row in actions.items() if row["action"] == "delete"} == {"artifacts/recent"}
    assert actions["smoke/p/recent"]["reason"] == "within_ttl:1d"
    assert actions["checks/today/recent.json"]["reason"] == "within_ttl:1d"
    assert actions["artifacts/pinned"]["reason"] == "pinned_item"
    assert plan["summary"]["delete_bytes"] == 1 and entries == before


def test_default_anchor_is_an_observed_utc_time():
    before = datetime.now(UTC)
    plan = build_retention_plan([])
    after = datetime.now(UTC)
    assert before <= datetime.fromisoformat(plan["as_of"]) <= after
    assert plan["actions"] == []
