from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("reviewrun_consistency_test", str(path))
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


def _write_review_bundle(run_dir: Path, *, manifest_authoritative: bool = False) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "snapshot.json").write_text(
        json.dumps({"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}}),
        encoding="utf-8",
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": manifest_authoritative,
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
                "decision": "pass",
                "findings": [],
                "executed_checks": ["deterministic"],
                "deterministic_lane_version": "deterministic_v0",
            }
        ),
        encoding="utf-8",
    )


def test_signature_from_run_accepts_valid_review_bundle(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir)

    signature = module._signature_from_run(  # type: ignore[attr-defined]
        run_dir=run_dir,
        run_result={"snapshot_digest": "sha256:abc", "policy_digest": "sha256:def"},
    )

    assert signature["snapshot_digest"] == "sha256:abc"
    assert signature["policy_digest"] == "sha256:def"
    assert signature["decision"] == "pass"


def test_signature_from_run_rejects_drifted_review_bundle_markers(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir, manifest_authoritative=True)

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
        module._signature_from_run(  # type: ignore[attr-defined]
            run_dir=run_dir,
            run_result={"snapshot_digest": "sha256:abc", "policy_digest": "sha256:def"},
        )


def test_snapshot_truncation_from_run_accepts_valid_review_bundle(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir)

    truncation = module._snapshot_truncation_from_run(run_dir)  # type: ignore[attr-defined]

    assert truncation == {"diff_truncated": False}


def test_snapshot_truncation_from_run_rejects_drifted_review_bundle_markers(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir, manifest_authoritative=True)

    with pytest.raises(ValueError, match="review_run_manifest_execution_state_authoritative_invalid"):
        module._snapshot_truncation_from_run(run_dir)  # type: ignore[attr-defined]
