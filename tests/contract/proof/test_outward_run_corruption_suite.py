from __future__ import annotations

from scripts.proof.run_outward_run_corruption_suite import run_corruption_suite


def test_outward_run_corruption_suite_accepts_base_and_rejects_implemented_corruptions() -> None:
    """Layer: contract. Verifies the approved-path corruption suite is falsifiable over packages."""
    report = run_corruption_suite()

    assert report["base_result"] == "accepted"
    assert report["result"] == "accepted"
    assert report["failed_count"] == 0
    assert report["implemented_count"] >= 49
    blocked_ids = {row["corruption_id"] for row in report["rows"] if row["status"] == "blocked"}
    assert {"ORP-CORR-030", "ORP-CORR-031", "ORP-CORR-068"} <= blocked_ids
