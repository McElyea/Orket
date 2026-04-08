from __future__ import annotations

import pytest

from orket.application.review.lanes.model_assisted import run_model_assisted_lane
from orket.application.review.models import ChangedFile, ReviewSnapshot, SnapshotBounds, TruncationReport

pytestmark = pytest.mark.unit


def _snapshot() -> ReviewSnapshot:
    snapshot = ReviewSnapshot(
        source="diff",
        repo={"remote": "", "repo_id": "repo"},
        base_ref="base",
        head_ref="head",
        bounds=SnapshotBounds(),
        truncation=TruncationReport(notes=[]),
        changed_files=[ChangedFile(path="app.py", status="M", additions=1, deletions=0)],
        diff_unified="+print('hello')\n",
        context_blobs=[],
        metadata={},
    )
    snapshot.compute_snapshot_digest()
    return snapshot


def test_model_assisted_lane_propagates_provider_signature_type_error() -> None:
    """Layer: unit. Verifies wrong-callable provider TypeErrors remain programming errors."""

    def wrong_signature() -> dict[str, object]:
        return {}

    with pytest.raises(TypeError):
        run_model_assisted_lane(
            snapshot=_snapshot(),
            resolved_policy={"model_assisted": {"enabled": True, "model_id": "test-model"}},
            run_id="run-1",
            policy_digest="sha256:policy",
            provider=wrong_signature,
        )
