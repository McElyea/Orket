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


def test_review_run_result_rejects_manifest_run_id_mismatch() -> None:
    """Layer: contract. Verifies review result JSON fail-closes if embedded manifest run identity drifts."""
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
            "run_id": "run-2",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_run_id_mismatch"):
        result.to_dict()


def test_review_run_result_rejects_manifest_control_plane_run_id_mismatch() -> None:
    """Layer: contract. Verifies review result JSON fails closed if embedded manifest control-plane run identity drifts."""
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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-2",
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_control_plane_run_id_mismatch"):
        result.to_dict()


def test_review_run_result_rejects_missing_manifest_run_id() -> None:
    """Layer: contract. Verifies review result JSON fails closed if embedded manifest omits run identity."""
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
            "lane_outputs_execution_state_authoritative": False,
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_run_id_required"):
        result.to_dict()


def test_review_run_result_rejects_missing_result_run_id() -> None:
    """Layer: contract. Verifies review result JSON fails closed if top-level review run identity is empty."""
    result = ReviewRunResult(
        ok=True,
        run_id="",
        artifact_dir="workspace/default/review_runs/run-1",
        snapshot_digest="sha256:snapshot",
        policy_digest="sha256:policy",
        deterministic_decision="pass",
        deterministic_findings=0,
        model_assisted_enabled=False,
        manifest={
            "run_id": "",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
        },
    )

    with pytest.raises(ValueError, match="review_run_result_run_id_required"):
        result.to_dict()


@pytest.mark.parametrize(
    ("manifest_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
            },
            "review_run_manifest_control_plane_run_id_required",
        ),
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "",
                "control_plane_step_id": "run-1:step:start",
            },
            "review_run_manifest_control_plane_attempt_id_required",
        ),
    ],
)
def test_review_run_result_rejects_orphaned_manifest_control_plane_identifier_hierarchy(
    manifest_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if embedded manifest keeps lower-level ids after parents drop."""
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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            **manifest_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()


@pytest.mark.parametrize(
    ("manifest_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-2:attempt:0001",
            },
            "review_run_manifest_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-2:step:start",
            },
            "review_run_manifest_control_plane_step_id_run_lineage_mismatch",
        ),
    ],
)
def test_review_run_result_rejects_manifest_control_plane_run_lineage_drift(
    manifest_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if embedded manifest refs drift outside the declared control-plane run lineage."""
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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            **manifest_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()


def test_review_run_result_rejects_control_plane_identifier_mismatch() -> None:
    """Layer: contract. Verifies review result JSON fail-closes if control-plane summary ids drift."""
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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        control_plane={
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": "run-1",
            "attempt_id": "run-1:attempt:9999",
            "attempt_ordinal": 1,
            "step_id": "run-1:step:start",
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_state": "attempt_completed",
            "policy_snapshot_id": "review-run-policy:run-1",
            "configuration_snapshot_id": "review-run-config:run-1",
            "step_kind": "review_run_start",
        },
    )

    with pytest.raises(ValueError, match="review_control_plane_attempt_id_mismatch"):
        result.to_dict()


def test_review_run_result_rejects_missing_manifest_control_plane_ref_when_projection_present() -> None:
    """Layer: contract. Verifies review result JSON fails closed if projected control-plane refs outlive embedded manifest refs."""
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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
        },
        control_plane={
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": "run-1",
            "attempt_id": "run-1:attempt:0001",
            "attempt_ordinal": 1,
            "step_id": "run-1:step:start",
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_state": "attempt_completed",
            "policy_snapshot_id": "review-run-policy:run-1",
            "configuration_snapshot_id": "review-run-config:run-1",
            "step_kind": "review_run_start",
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_control_plane_step_id_missing"):
        result.to_dict()


@pytest.mark.parametrize(
    ("control_plane_overrides", "expected_error"),
    [
        (
            {
                "run_id": "",
                "attempt_id": "run-1:attempt:0001",
                "step_id": "run-1:step:start",
            },
            "review_control_plane_run_id_required",
        ),
        (
            {
                "attempt_id": "",
                "step_id": "run-1:step:start",
            },
            "review_control_plane_attempt_id_required",
        ),
    ],
)
def test_review_run_result_rejects_orphaned_control_plane_identifier_hierarchy(
    control_plane_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if lower-level projected ids outlive their parent ids."""
    control_plane = {
        "projection_source": "control_plane_records",
        "projection_only": True,
        "run_id": "run-1",
        "attempt_id": "run-1:attempt:0001",
        "attempt_ordinal": 1,
        "step_id": "run-1:step:start",
        "run_state": "completed",
        "workload_id": "review.run",
        "workload_version": "v0",
        "attempt_state": "attempt_completed",
        "policy_snapshot_id": "review-run-policy:run-1",
        "configuration_snapshot_id": "review-run-config:run-1",
        "step_kind": "review_run_start",
    }
    control_plane.update(control_plane_overrides)

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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        control_plane=control_plane,
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()


@pytest.mark.parametrize(
    ("control_plane_overrides", "expected_error"),
    [
        (
            {
                "attempt_id": "",
                "attempt_state": "attempt_completed",
                "attempt_ordinal": "",
                "step_id": "",
                "step_kind": "",
            },
            "review_control_plane_attempt_id_required",
        ),
        (
            {
                "attempt_id": "",
                "attempt_state": "",
                "attempt_ordinal": 1,
                "step_id": "",
                "step_kind": "",
            },
            "review_control_plane_attempt_id_required",
        ),
        (
            {
                "step_id": "",
                "step_kind": "review_run_start",
            },
            "review_control_plane_step_id_required",
        ),
    ],
)
def test_review_run_result_rejects_orphaned_control_plane_projection_metadata(
    control_plane_overrides: dict[str, object],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if attempt or step metadata survives after its projected id drops."""
    control_plane = {
        "projection_source": "control_plane_records",
        "projection_only": True,
        "run_id": "run-1",
        "attempt_id": "run-1:attempt:0001",
        "attempt_ordinal": 1,
        "step_id": "run-1:step:start",
        "run_state": "completed",
        "workload_id": "review.run",
        "workload_version": "v0",
        "attempt_state": "attempt_completed",
        "policy_snapshot_id": "review-run-policy:run-1",
        "configuration_snapshot_id": "review-run-config:run-1",
        "step_kind": "review_run_start",
    }
    control_plane.update(control_plane_overrides)

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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        control_plane=control_plane,
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()


@pytest.mark.parametrize(
    ("control_plane_overrides", "expected_error"),
    [
        (
            {"attempt_id": "run-2:attempt:0001"},
            "review_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            {"step_id": "run-2:step:start"},
            "review_control_plane_step_id_run_lineage_mismatch",
        ),
    ],
)
def test_review_run_result_rejects_control_plane_run_lineage_drift(
    control_plane_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if projected refs drift outside the projected run lineage."""
    control_plane = {
        "projection_source": "control_plane_records",
        "projection_only": True,
        "run_id": "run-1",
        "attempt_id": "run-1:attempt:0001",
        "attempt_ordinal": 1,
        "step_id": "run-1:step:start",
        "run_state": "completed",
        "workload_id": "review.run",
        "workload_version": "v0",
        "attempt_state": "attempt_completed",
        "policy_snapshot_id": "review-run-policy:run-1",
        "configuration_snapshot_id": "review-run-config:run-1",
        "step_kind": "review_run_start",
    }
    control_plane.update(control_plane_overrides)

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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        control_plane=control_plane,
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()


@pytest.mark.parametrize(
    ("control_plane_overrides", "expected_error"),
    [
        ({"workload_id": ""}, "review_control_plane_workload_id_required"),
        ({"attempt_state": ""}, "review_control_plane_attempt_state_required"),
        ({"attempt_ordinal": None}, "review_control_plane_attempt_ordinal_required"),
        ({"step_kind": ""}, "review_control_plane_step_kind_required"),
    ],
)
def test_review_run_result_rejects_incomplete_control_plane_lifecycle_projection(
    control_plane_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies review result JSON fails closed if projected lifecycle state is incomplete."""
    control_plane = {
        "projection_source": "control_plane_records",
        "projection_only": True,
        "run_id": "run-1",
        "attempt_id": "run-1:attempt:0001",
        "attempt_ordinal": 1,
        "step_id": "run-1:step:start",
        "run_state": "completed",
        "workload_id": "review.run",
        "workload_version": "v0",
        "attempt_state": "attempt_completed",
        "policy_snapshot_id": "review-run-policy:run-1",
        "configuration_snapshot_id": "review-run-config:run-1",
        "step_kind": "review_run_start",
    }
    control_plane.update(control_plane_overrides)

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
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
        control_plane=control_plane,
    )

    with pytest.raises(ValueError, match=expected_error):
        result.to_dict()
