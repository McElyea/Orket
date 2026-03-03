from __future__ import annotations

import json
from pathlib import Path

from orket.kernel.v1.nervous_system_policy_snapshot import (
    CANONICALIZER,
    DIGEST_ALGORITHM,
    build_policy_digest_snapshot,
)

SNAPSHOT_PATH = Path("tests/fixtures/nervous_system_policy_digest_snapshot.json")


def _load_snapshot() -> dict[str, object]:
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def test_policy_snapshot_metadata_shape_locked() -> None:
    current = build_policy_digest_snapshot()
    assert current["digest_algorithm"] == DIGEST_ALGORITHM
    assert current["canonicalizer"] == CANONICALIZER
    assert str(current["canonicalizer"]).startswith("orket/kernel/v1/canonical.py@")


def test_policy_and_tool_profile_digest_snapshot() -> None:
    snapshot = _load_snapshot()
    expected = build_policy_digest_snapshot()
    assert snapshot == expected, (
        "Nervous-system policy snapshot drift detected. If this change is intentional, run "
        "python scripts/update_nervous_system_policy_digest_snapshot.py"
    )
