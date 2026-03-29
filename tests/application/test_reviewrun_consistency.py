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


def _write_review_bundle(
    run_dir: Path,
    *,
    manifest_authoritative: bool = False,
    manifest_overrides: dict | None = None,
    deterministic_overrides: dict | None = None,
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "snapshot.json").write_text(
        json.dumps({"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}}),
        encoding="utf-8",
    )
    (run_dir / "run_manifest.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": manifest_authoritative,
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
                **dict(manifest_overrides or {}),
            }
        ),
        encoding="utf-8",
    )
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
                "decision": "pass",
                "findings": [],
                "executed_checks": ["deterministic"],
                "deterministic_lane_version": "deterministic_v0",
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
                **dict(deterministic_overrides or {}),
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


def test_signature_from_run_rejects_drifted_review_bundle_identifiers(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir)
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
                "decision": "pass",
                "findings": [],
                "executed_checks": ["deterministic"],
                "deterministic_lane_version": "deterministic_v0",
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:9999",
                "control_plane_step_id": "run-1:step:start",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_attempt_id_mismatch"):
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


def test_snapshot_truncation_from_run_rejects_missing_review_bundle_control_plane_ref(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(run_dir)
    (run_dir / "deterministic_decision.json").write_text(
        json.dumps(
            {
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_output_execution_state_authoritative": False,
                "decision": "pass",
                "findings": [],
                "executed_checks": ["deterministic"],
                "deterministic_lane_version": "deterministic_v0",
                "control_plane_run_id": "run-1",
                "control_plane_step_id": "run-1:step:start",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_attempt_id_missing"):
        module._snapshot_truncation_from_run(run_dir)  # type: ignore[attr-defined]


def test_snapshot_truncation_from_run_rejects_orphaned_review_bundle_control_plane_ref(tmp_path: Path) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    run_dir = tmp_path / "run"
    _write_review_bundle(
        run_dir,
        manifest_overrides={
            "control_plane_run_id": "",
            "control_plane_attempt_id": "",
            "control_plane_step_id": "",
        },
        deterministic_overrides={
            "control_plane_attempt_id": "",
            "control_plane_step_id": "run-1:step:start",
        },
    )

    with pytest.raises(ValueError, match="deterministic_review_decision_control_plane_attempt_id_missing"):
        module._snapshot_truncation_from_run(run_dir)  # type: ignore[attr-defined]


def test_validated_report_run_id_rejects_missing_run_id() -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))

    with pytest.raises(ValueError, match="reviewrun_consistency_default_run_id_required"):
        module._validated_report_run_id({}, field_name="reviewrun_consistency_default")  # type: ignore[attr-defined]


def test_main_rejects_missing_default_run_id_before_writing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    fixture_root = tmp_path / "fixture-root"
    workspace = tmp_path / "workspace"
    out_path = tmp_path / "reviewrun_consistency.json"

    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix="": str(fixture_root))
    monkeypatch.setattr(module, "_seed_repo_for_constants_diff", lambda repo: ("base", "head"))

    class _FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, object]:
            return dict(self._payload)

    class _FakeService:
        def __init__(self, *, workspace: Path) -> None:
            self.workspace = workspace

        def run_diff(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "",
                    "artifact_dir": str(tmp_path / "unused-run"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

        def replay(self, **_: object) -> _FakeResponse:
            raise AssertionError("replay should not be reached when default run_id is missing")

    monkeypatch.setattr(module, "ReviewRunService", _FakeService)
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            runs=1,
            out=str(out_path),
            workspace=str(workspace),
            keep_fixture=True,
            keep_runs=True,
            scenario="constants_flags",
        ),
    )

    with pytest.raises(ValueError, match="reviewrun_consistency_default_run_id_required"):
        module.main()

    assert out_path.exists() is False


def test_main_rejects_consistency_report_contract_drift_before_writing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    fixture_root = tmp_path / "fixture-root"
    workspace = tmp_path / "workspace"
    out_path = tmp_path / "reviewrun_consistency.json"

    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix="": str(fixture_root))
    monkeypatch.setattr(module, "_seed_repo_for_constants_diff", lambda repo: ("base", "head"))
    monkeypatch.setattr(module, "_signature_from_run", lambda **_: {"decision": "accept", "findings": []})
    monkeypatch.setattr(
        module,
        "load_validated_review_run_bundle_artifacts",
        lambda *_, **__: {
            "snapshot": {"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}},
            "policy_resolved": {"policy_digest": "sha256:def"},
        },
    )
    monkeypatch.setattr(module, "REPORT_CONTRACT_VERSION", "drifted")

    class _FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, object]:
            return dict(self._payload)

    class _FakeService:
        def __init__(self, *, workspace: Path) -> None:
            self.workspace = workspace

        def run_diff(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-run"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

        def replay(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-replay"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

    monkeypatch.setattr(module, "ReviewRunService", _FakeService)
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            runs=1,
            out=str(out_path),
            workspace=str(workspace),
            keep_fixture=True,
            keep_runs=True,
            scenario="constants_flags",
        ),
    )

    with pytest.raises(ValueError, match="reviewrun_consistency_contract_version_invalid"):
        module.main()

    assert out_path.exists() is False


def test_main_rejects_consistency_signature_contract_drift_before_writing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    fixture_root = tmp_path / "fixture-root"
    workspace = tmp_path / "workspace"
    out_path = tmp_path / "reviewrun_consistency.json"

    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix="": str(fixture_root))
    monkeypatch.setattr(module, "_seed_repo_for_constants_diff", lambda repo: ("base", "head"))
    monkeypatch.setattr(
        module,
        "_signature_from_run",
        lambda **_: {
            "snapshot_digest": "sha256:abc",
            "policy_digest": "sha256:def",
            "deterministic_lane_version": "deterministic_v0",
            "decision": "accept",
            "findings": [],
            "executed_checks": "",
            "truncation": {"diff_truncated": False},
        },
    )
    monkeypatch.setattr(
        module,
        "load_validated_review_run_bundle_artifacts",
        lambda *_, **__: {
            "snapshot": {"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}},
            "policy_resolved": {"policy_digest": "sha256:def"},
        },
    )

    class _FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, object]:
            return dict(self._payload)

    class _FakeService:
        def __init__(self, *, workspace: Path) -> None:
            self.workspace = workspace

        def run_diff(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-run"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

        def replay(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-replay"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

    monkeypatch.setattr(module, "ReviewRunService", _FakeService)
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            runs=1,
            out=str(out_path),
            workspace=str(workspace),
            keep_fixture=True,
            keep_runs=True,
            scenario="constants_flags",
        ),
    )

    with pytest.raises(ValueError, match="reviewrun_consistency_default_signature_executed_checks_invalid"):
        module.main()

    assert out_path.exists() is False


# Layer: integration
def test_main_rejects_consistency_finding_row_contract_drift_before_writing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    fixture_root = tmp_path / "fixture-root"
    workspace = tmp_path / "workspace"
    out_path = tmp_path / "reviewrun_consistency.json"

    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix="": str(fixture_root))
    monkeypatch.setattr(module, "_seed_repo_for_constants_diff", lambda repo: ("base", "head"))
    monkeypatch.setattr(
        module,
        "_signature_from_run",
        lambda **_: {
            "snapshot_digest": "sha256:abc",
            "policy_digest": "sha256:def",
            "deterministic_lane_version": "deterministic_v0",
            "decision": "accept",
            "findings": [
                {
                    "code": "PATTERN_MATCHED",
                    "severity": "high",
                    "message": "",
                    "path": "app/config.py",
                    "span": {"start": 1, "end": 1},
                    "details": {"pattern": "debug"},
                }
            ],
            "executed_checks": ["deterministic"],
            "truncation": {"diff_truncated": False},
        },
    )
    monkeypatch.setattr(
        module,
        "load_validated_review_run_bundle_artifacts",
        lambda *_, **__: {
            "snapshot": {"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}},
            "policy_resolved": {"policy_digest": "sha256:def"},
        },
    )

    class _FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, object]:
            return dict(self._payload)

    class _FakeService:
        def __init__(self, *, workspace: Path) -> None:
            self.workspace = workspace

        def run_diff(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-run"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

        def replay(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-replay"),
                    "snapshot_digest": "sha256:abc",
                    "policy_digest": "sha256:def",
                }
            )

    monkeypatch.setattr(module, "ReviewRunService", _FakeService)
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            runs=1,
            out=str(out_path),
            workspace=str(workspace),
            keep_fixture=True,
            keep_runs=True,
            scenario="constants_flags",
        ),
    )

    with pytest.raises(ValueError, match="reviewrun_consistency_default_signature_findings_message_invalid"):
        module.main()

    assert out_path.exists() is False


# Layer: integration
def test_main_rejects_truncation_check_contract_drift_before_writing_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_module(Path("scripts/reviewrun/run_1000_consistency.py"))
    fixture_root = tmp_path / "fixture-root"
    workspace = tmp_path / "workspace"
    out_path = tmp_path / "reviewrun_consistency.json"

    monkeypatch.setattr(module.tempfile, "mkdtemp", lambda prefix="": str(fixture_root))
    monkeypatch.setattr(module, "_seed_repo_for_constants_diff", lambda repo: ("base", "head"))
    monkeypatch.setattr(
        module,
        "_signature_from_run",
        lambda **_: {
            "snapshot_digest": "sha256:abc",
            "policy_digest": "sha256:def",
            "deterministic_lane_version": "deterministic_v0",
            "decision": "accept",
            "findings": [],
            "executed_checks": ["deterministic"],
            "truncation": {"diff_truncated": False},
        },
    )
    monkeypatch.setattr(
        module,
        "_snapshot_truncation_from_run",
        lambda *_args, **_kwargs: {
            "diff_truncated": True,
            "diff_bytes_original": 1000,
            "diff_bytes_kept": 300,
        },
    )
    monkeypatch.setattr(
        module,
        "load_validated_review_run_bundle_artifacts",
        lambda *_, **__: {
            "snapshot": {"snapshot_digest": "sha256:abc", "truncation": {"diff_truncated": False}},
            "policy_resolved": {"policy_digest": "sha256:def"},
        },
    )

    class _FakeResponse:
        def __init__(self, payload: dict[str, object]) -> None:
            self._payload = payload

        def to_dict(self) -> dict[str, object]:
            return dict(self._payload)

    class _FakeService:
        def __init__(self, *, workspace: Path) -> None:
            self.workspace = workspace

        def run_diff(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-run"),
                    "snapshot_digest": "",
                    "policy_digest": "sha256:def",
                }
            )

        def replay(self, **_: object) -> _FakeResponse:
            return _FakeResponse(
                {
                    "run_id": "run-1",
                    "artifact_dir": str(tmp_path / "unused-replay"),
                    "snapshot_digest": "",
                    "policy_digest": "sha256:def",
                }
            )

    monkeypatch.setattr(module, "ReviewRunService", _FakeService)
    monkeypatch.setattr(
        module.argparse.ArgumentParser,
        "parse_args",
        lambda self: module.argparse.Namespace(
            runs=1,
            out=str(out_path),
            workspace=str(workspace),
            keep_fixture=True,
            keep_runs=True,
            scenario="truncation_bounds",
        ),
    )

    with pytest.raises(ValueError, match="reviewrun_consistency_truncation_check_unbounded_snapshot_digest_invalid"):
        module.main()

    assert out_path.exists() is False
