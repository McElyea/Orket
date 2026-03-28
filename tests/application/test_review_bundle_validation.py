# Layer: unit
from __future__ import annotations

import json
from pathlib import Path

import pytest

from orket.application.review.bundle_validation import (
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
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": manifest_authoritative,
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
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "decision": "pass",
        },
    )
    _write_json(
        run_dir / "model_assisted_critique.json",
        {
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "summary": ["ok"],
        },
    )


def test_load_validated_review_run_bundle_payloads_returns_authority_checked_payloads(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir)

    payloads = load_validated_review_run_bundle_payloads(run_dir)

    assert payloads["manifest"] == {
        "execution_state_authority": "control_plane_records",
        "lane_outputs_execution_state_authoritative": False,
    }
    assert payloads["deterministic"] == {
        "execution_state_authority": "control_plane_records",
        "lane_output_execution_state_authoritative": False,
        "decision": "pass",
    }
    assert payloads["model_assisted"] == {
        "execution_state_authority": "control_plane_records",
        "lane_output_execution_state_authoritative": False,
        "summary": ["ok"],
    }


def test_load_validated_review_run_bundle_payloads_rejects_drifted_markers(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _write_valid_bundle(run_dir, manifest_authoritative=True)

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
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
