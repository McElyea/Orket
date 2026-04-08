from __future__ import annotations

import hashlib

from orket.application.review.lanes.deterministic import run_deterministic_lane
from orket.application.review.models import ChangedFile, ReviewSnapshot, SnapshotBounds, TruncationReport
from orket.application.review.policy_resolver import DEFAULT_POLICY


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
    snap = _snapshot(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -0,0 +1 @@\n"
        "+password = 1\n"
    )
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


def test_default_todo_forbidden_pattern_is_info_severity() -> None:
    """Layer: unit. Verifies broad TODO/FIXME defaults do not block otherwise-valid review diffs."""
    snap = _snapshot(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -0,0 +1 @@\n"
        "+# TODO: add more tests\n"
    )

    result = run_deterministic_lane(
        snapshot=snap,
        resolved_policy=DEFAULT_POLICY,
        run_id="R1",
        policy_digest="sha256:abc",
    )

    todo_finding = next(
        item for item in result.findings if (item.details or {}).get("pattern") == r"(?i)\b(todo|fixme)\b"
    )
    assert todo_finding.severity == "info"
    assert result.decision == "pass"


def test_deterministic_lane_ignores_removed_forbidden_patterns() -> None:
    """Layer: unit. Verifies removed forbidden text does not trigger an introduced-pattern finding."""
    policy = {
        "deterministic": {
            "checks": {
                "forbidden_patterns": ["password\\s*="],
            }
        }
    }
    snap = _snapshot(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,2 +1,2 @@\n"
        '-password = "secret"\n'
        '+token = get_from_vault()\n'
    )

    result = run_deterministic_lane(snapshot=snap, resolved_policy=policy, run_id="R1", policy_digest="sha256:abc")

    assert not any(item.code == "PATTERN_MATCHED" for item in result.findings)


def test_default_password_policy_requires_string_literal_assignment() -> None:
    """Layer: unit. Verifies the default password policy does not flag dynamic secret retrieval."""
    snap = _snapshot(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -0,0 +1 @@\n"
        "+password = get_from_vault()\n"
    )

    result = run_deterministic_lane(
        snapshot=snap,
        resolved_policy=DEFAULT_POLICY,
        run_id="R1",
        policy_digest="sha256:abc",
    )

    assert not any(
        (item.details or {}).get("pattern") == r"(?i)password\s*=\s*['\"](?!\s*['\"])"
        for item in result.findings
    )


def test_deterministic_lane_caps_forbidden_pattern_occurrences() -> None:
    """Layer: unit. Verifies forbidden-pattern reporting stays bounded when a pattern matches many added lines."""
    policy = {
        "deterministic": {
            "checks": {
                "forbidden_patterns": [
                    {"pattern": "secret", "severity": "high", "max_occurrences": 2},
                ],
            }
        }
    }
    snap = _snapshot(
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -0,0 +1,3 @@\n"
        '+token = "secret-1"\n'
        '+token = "secret-2"\n'
        '+token = "secret-3"\n'
    )

    result = run_deterministic_lane(snapshot=snap, resolved_policy=policy, run_id="R1", policy_digest="sha256:abc")

    matched = [item for item in result.findings if item.code == "PATTERN_MATCHED"]
    assert len(matched) == 2
    assert [item.span["start"] for item in matched] == [1, 2]
