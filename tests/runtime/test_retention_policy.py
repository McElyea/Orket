from __future__ import annotations

from datetime import UTC, datetime

from orket.runtime.retention_policy import RetentionPolicy, build_retention_plan


def _action_map(plan: dict) -> dict[str, dict]:
    return {row["path"]: row for row in plan["actions"]}


def test_retention_policy_preserves_latest_and_pinned_and_newest_groups():
    entries = [
        {"path": "latest/smoke/api-runtime/latest.json", "updated_at": "2026-02-24T10:00:00+00:00", "size_bytes": 1},
        {"path": "smoke/api-runtime/2026-01-01/run-a.json", "updated_at": "2026-01-01T00:00:00+00:00", "size_bytes": 1},
        {"path": "smoke/api-runtime/2026-02-24/run-b.json", "updated_at": "2026-02-24T00:00:00+00:00", "size_bytes": 1},
        {
            "path": "checks/2026-02-20/check_alpha_pass.json",
            "updated_at": "2026-02-20T00:00:00+00:00",
            "size_bytes": 1,
            "status": "pass",
        },
        {
            "path": "checks/2025-10-01/check_alpha_pass_old.json",
            "updated_at": "2025-10-01T00:00:00+00:00",
            "size_bytes": 1,
            "status": "pass",
        },
        {
            "path": "artifacts/2025-01-01/run-heavy.bin",
            "updated_at": "2025-01-01T00:00:00+00:00",
            "size_bytes": 10,
            "pinned": True,
        },
    ]
    plan = build_retention_plan(
        entries,
        as_of=datetime(2026, 2, 24, tzinfo=UTC),
        policy=RetentionPolicy(
            smoke_days=14,
            smoke_keep_latest_per_profile=1,
            checks_days=60,
            artifacts_days=30,
            artifacts_size_cap_bytes=1,
        ),
    )
    actions = _action_map(plan)
    assert actions["latest/smoke/api-runtime/latest.json"]["action"] == "keep"
    assert actions["artifacts/2025-01-01/run-heavy.bin"]["action"] == "keep"
    assert actions["smoke/api-runtime/2026-02-24/run-b.json"]["action"] == "keep"
    assert actions["smoke/api-runtime/2026-01-01/run-a.json"]["action"] == "delete"
    assert actions["checks/2026-02-20/check_alpha_pass.json"]["action"] == "keep"
    assert actions["checks/2025-10-01/check_alpha_pass_old.json"]["action"] == "delete"


def test_artifact_size_cap_prunes_oldest_unpinned():
    entries = [
        {"path": "artifacts/2026-02-23/a.bin", "updated_at": "2026-02-23T00:00:00+00:00", "size_bytes": 10},
        {"path": "artifacts/2026-02-22/b.bin", "updated_at": "2026-02-22T00:00:00+00:00", "size_bytes": 10},
        {"path": "artifacts/2026-02-21/c.bin", "updated_at": "2026-02-21T00:00:00+00:00", "size_bytes": 10},
    ]
    plan = build_retention_plan(
        entries,
        as_of=datetime(2026, 2, 24, tzinfo=UTC),
        policy=RetentionPolicy(
            smoke_days=14,
            smoke_keep_latest_per_profile=50,
            checks_days=60,
            artifacts_days=365,
            artifacts_size_cap_bytes=20,
        ),
    )
    actions = _action_map(plan)
    assert actions["artifacts/2026-02-23/a.bin"]["action"] == "keep"
    assert actions["artifacts/2026-02-22/b.bin"]["action"] == "keep"
    assert actions["artifacts/2026-02-21/c.bin"]["action"] == "delete"

