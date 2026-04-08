# Layer: unit
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.review.bundle_validation import (
    ReviewBundleError,
    load_validated_review_run_bundle_artifacts,
    load_validated_review_run_bundle_payloads,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_valid_bundle(run_dir: Path, *, manifest_authoritative: bool = False) -> None:
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": manifest_authoritative,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )
    _write_json(
        run_dir / "snapshot.json",
        {
            "source": "diff",
            "repo": {},
            "base_ref": "base",
            "head_ref": "head",
            "bounds": {},
            "truncation": {},
            "changed_files": [],
            "diff_unified": "",
            "context_blobs": [],
            "metadata": {},
            "snapshot_digest": "sha256:test",
        },
    )
    _write_json(
        run_dir / "policy_resolved.json",
        {
            "policy_digest": "sha256:policy",
            "review_policy_version": "review_policy_v0",
        },
    )
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )
    _write_json(
        run_dir / "model_assisted_critique.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "summary": ["ok"],
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )


def test_load_validated_review_run_bundle_payloads_returns_authority_checked_payloads(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)

    payloads = load_validated_review_run_bundle_payloads(run_dir)

    assert payloads["manifest"] == {
        "run_id": "run-1",
        "execution_state_authority": "control_plane_records",
        "lane_outputs_execution_state_authoritative": False,
        "control_plane_run_id": "run-1",
        "control_plane_attempt_id": "run-1:attempt:0001",
        "control_plane_step_id": "run-1:step:start",
    }
    assert payloads["deterministic"] == {
        "run_id": "run-1",
        "execution_state_authority": "control_plane_records",
        "lane_output_execution_state_authoritative": False,
        "decision": "pass",
        "control_plane_run_id": "run-1",
        "control_plane_attempt_id": "run-1:attempt:0001",
        "control_plane_step_id": "run-1:step:start",
    }
    assert payloads["model_assisted"] == {
        "run_id": "run-1",
        "execution_state_authority": "control_plane_records",
        "lane_output_execution_state_authoritative": False,
        "summary": ["ok"],
        "control_plane_run_id": "run-1",
        "control_plane_attempt_id": "run-1:attempt:0001",
        "control_plane_step_id": "run-1:step:start",
    }


def test_load_validated_review_run_bundle_payloads_rejects_drifted_markers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir, manifest_authoritative=True)

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_payloads_rejects_identifier_drift(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:9999",
            "control_plane_step_id": "run-1:step:start",
        },
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_attempt_id_mismatch"):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_payloads_rejects_control_plane_run_id_drift(tmp_path: Path) -> None:
    """Layer: contract. Verifies persisted review bundle validation fails closed on same-run control-plane run drift."""
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            "control_plane_run_id": "run-2",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_run_id_mismatch"):
        load_validated_review_run_bundle_payloads(run_dir)


@pytest.mark.parametrize(
    ("payload_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-2:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
            },
            "deterministic_review_decision_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-2:step:start",
            },
            "deterministic_review_decision_control_plane_step_id_run_lineage_mismatch",
        ),
    ],
)
def test_load_validated_review_run_bundle_payloads_rejects_lane_control_plane_run_lineage_drift(
    tmp_path: Path,
    payload_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies persisted review bundle validation rejects lane refs that drift outside the declared control-plane run lineage."""
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            **payload_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_payloads_rejects_missing_lane_run_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_run_id_missing"):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_payloads_rejects_missing_manifest_run_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
            "control_plane_step_id": "run-1:step:start",
        },
    )

    with pytest.raises(ValueError, match="review_run_manifest_run_id_missing"):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_payloads_rejects_missing_lane_control_plane_step_id(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            "control_plane_run_id": "run-1",
            "control_plane_attempt_id": "run-1:attempt:0001",
        },
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_step_id_missing"):
        load_validated_review_run_bundle_payloads(run_dir)


@pytest.mark.parametrize(
    ("payload_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
            },
            "deterministic_review_decision_control_plane_run_id_missing",
        ),
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "",
                "control_plane_step_id": "run-1:step:start",
            },
            "deterministic_review_decision_control_plane_attempt_id_missing",
        ),
    ],
)
def test_load_validated_review_run_bundle_payloads_rejects_orphaned_lane_control_plane_refs(
    tmp_path: Path,
    payload_overrides: dict[str, str],
    expected_error: str,
) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
        },
    )
    _write_json(
        run_dir / "deterministic_decision.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
            **payload_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        load_validated_review_run_bundle_payloads(run_dir)


@pytest.mark.parametrize(
    ("manifest_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
            },
            "review_run_manifest_control_plane_run_id_missing",
        ),
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "",
                "control_plane_step_id": "run-1:step:start",
            },
            "review_run_manifest_control_plane_attempt_id_missing",
        ),
    ],
)
def test_load_validated_review_run_bundle_payloads_rejects_orphaned_manifest_control_plane_refs(
    tmp_path: Path,
    manifest_overrides: dict[str, str],
    expected_error: str,
) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            **manifest_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        load_validated_review_run_bundle_payloads(run_dir)


@pytest.mark.parametrize(
    ("manifest_overrides", "expected_error"),
    [
        (
            {
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-2:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
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
def test_load_validated_review_run_bundle_payloads_rejects_manifest_control_plane_run_lineage_drift(
    tmp_path: Path,
    manifest_overrides: dict[str, str],
    expected_error: str,
) -> None:
    """Layer: contract. Verifies persisted review bundle validation rejects manifest refs that drift outside the declared control-plane run lineage."""
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
            **manifest_overrides,
        },
    )

    with pytest.raises(ValueError, match=expected_error):
        load_validated_review_run_bundle_payloads(run_dir)


def test_load_validated_review_run_bundle_artifacts_returns_snapshot_and_policy(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)

    artifacts = load_validated_review_run_bundle_artifacts(run_dir, require_policy_resolved=True)

    assert artifacts["snapshot"] == {
        "source": "diff",
        "repo": {},
        "base_ref": "base",
        "head_ref": "head",
        "bounds": {},
        "truncation": {},
        "changed_files": [],
        "diff_unified": "",
        "context_blobs": [],
        "metadata": {},
        "snapshot_digest": "sha256:test",
    }
    assert artifacts["policy_resolved"] == {
        "policy_digest": "sha256:policy",
        "review_policy_version": "review_policy_v0",
    }


def test_load_validated_review_run_bundle_artifacts_requires_policy_when_requested(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    (run_dir / "policy_resolved.json").unlink()

    with pytest.raises(ValueError, match="review_run_resolved_policy_missing"):
        load_validated_review_run_bundle_artifacts(run_dir, require_policy_resolved=True)


def test_review_bundle_error_exposes_error_code_and_field(tmp_path: Path) -> None:
    """Layer: unit. Verifies review bundle validation failures use the typed error surface."""
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)
    (run_dir / "policy_resolved.json").unlink()

    with pytest.raises(ReviewBundleError) as exc_info:
        load_validated_review_run_bundle_artifacts(run_dir, require_policy_resolved=True)

    assert exc_info.value.error_code == "review_run_resolved_policy_missing"
    assert exc_info.value.field == "review_run_resolved_policy"
