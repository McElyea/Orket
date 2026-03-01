from __future__ import annotations

import hashlib

from orket.application.review.lanes.deterministic import run_deterministic_lane
from orket.application.review.models import ChangedFile, ReviewSnapshot, SnapshotBounds, TruncationReport


def _snapshot(diff: str) -> ReviewSnapshot:
    snap = ReviewSnapshot(
        source="diff",
        repo={"remote": "", "repo_id": "repo"},
        base_ref="a",
        head_ref="b",
        bounds=SnapshotBounds(),
        truncation=TruncationReport(),
        changed_files=[ChangedFile(path="src/app.py", status="M", additions=1, deletions=0)],
        diff_unified=diff,
        context_blobs=[],
        metadata={},
    )
    snap.compute_snapshot_digest()
    return snap


def test_deterministic_lane_reproducible_and_sorted() -> None:
    policy = {
        "deterministic": {
            "checks": {
                "path_blocklist": ["src/"],
                "forbidden_patterns": ["password\\s*="],
                "test_hint_required_roots": ["src/"],
                "test_hint_test_roots": ["tests/"],
            }
        }
    }
    snap = _snapshot("password = 1\n")
    first = run_deterministic_lane(snapshot=snap, resolved_policy=policy, run_id="R1", policy_digest="sha256:abc")
    second = run_deterministic_lane(snapshot=snap, resolved_policy=policy, run_id="R1", policy_digest="sha256:abc")
    assert first.decision == second.decision
    assert [f.to_dict() for f in first.findings] == [f.to_dict() for f in second.findings]

    def key(item):
        return (
            -{"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}[item.severity],
            item.code,
            item.path if item.path else "\uffff",
            int((item.span or {}).get("start") or 0),
            hashlib.sha256(item.message.encode("utf-8")).hexdigest(),
        )

    assert [key(item) for item in first.findings] == sorted([key(item) for item in first.findings])
