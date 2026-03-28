from __future__ import annotations

import pytest

from orket.application.review.models import ReviewRunResult


def test_review_run_result_rejects_malformed_manifest_authority_markers() -> None:
    """Layer: contract. Verifies review result JSON fail-closes if embedded manifest authority markers drift."""
    result = ReviewRunResult(
        ok=True,
        run_id="run-1",
        artifact_dir="workspace/default/review_runs/run-1",
        snapshot_digest="sha256:snapshot",
        policy_digest="sha256:policy",
        deterministic_decision="pass",
        deterministic_findings=0,
        model_assisted_enabled=False,
        manifest={
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": True,
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
        result.to_dict()
