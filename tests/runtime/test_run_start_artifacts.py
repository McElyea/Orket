from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: unit
def test_capture_run_start_artifacts_writes_required_run_start_files(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "a.txt").parent.mkdir(parents=True, exist_ok=True)
    (workspace / "a.txt").write_text("alpha", encoding="utf-8")
    payload = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-1",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    assert payload["run_identity"]["run_id"] == "run-1"
    assert payload["run_identity"]["workload"] == "core_epic"
    assert payload["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")
    assert payload["run_determinism_class"] == "workspace"
    assert payload["run_phase_contract"]["schema_version"] == "1.0"
    assert payload["run_phase_contract"]["entry_phase"] == "input_normalize"
    assert payload["run_phase_contract"]["terminal_phase"] == "emit_observability"
    assert payload["runtime_status_vocabulary"]["schema_version"] == "1.0"
    assert "terminal_failure" in payload["runtime_status_vocabulary"]["runtime_status_terms"]
    assert payload["degradation_taxonomy"]["schema_version"] == "1.0"
    assert payload["fail_behavior_registry"]["schema_version"] == "1.0"
    assert Path(payload["run_identity_path"]).exists()
    assert Path(payload["run_phase_contract_path"]).exists()
    assert Path(payload["runtime_status_vocabulary_path"]).exists()
    assert Path(payload["degradation_taxonomy_path"]).exists()
    assert Path(payload["fail_behavior_registry_path"]).exists()
    assert Path(payload["ledger_event_schema_path"]).exists()
    assert Path(payload["capability_manifest_schema_path"]).exists()
    assert Path(payload["capability_manifest_path"]).exists()
    assert Path(payload["compatibility_map_snapshot_path"]).exists()
    assert Path(payload["workspace_state_snapshot_path"]).exists()
    workspace_snapshot = payload["workspace_state_snapshot"]
    assert workspace_snapshot["workspace_type"] == "filesystem"
    assert workspace_snapshot["workspace_path"] == str(workspace.resolve())
    assert workspace_snapshot["file_count"] == 1
    assert len(str(workspace_snapshot["workspace_hash"])) == 64


# Layer: contract
def test_capture_run_start_artifacts_reuses_existing_run_identity_for_same_run(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    first = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    second = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 18, 0, 0, tzinfo=UTC),
    )

    assert first["run_identity"] == second["run_identity"]
    assert first["run_identity"]["start_time"].startswith("2026-03-06T17:00:00")


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_identity_workload_mismatch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-mismatch",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="E_RUN_IDENTITY_IMMUTABLE:workload_mismatch"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-mismatch",
            workload="other_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_run_phase_contract_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-phase-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    run_phase_contract_path = (
        workspace
        / "observability"
        / "run-phase-immutable"
        / "runtime_contracts"
        / "run_phase_contract.json"
    )
    run_phase_contract_path.write_text(
        '{"schema_version":"999.0","entry_phase":"route","terminal_phase":"persist","canonical_phase_order":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_PHASE_CONTRACT_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-phase-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_runtime_status_vocabulary_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-status-vocab-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    runtime_status_vocabulary_path = (
        workspace
        / "observability"
        / "run-status-vocab-immutable"
        / "runtime_contracts"
        / "runtime_status_vocabulary.json"
    )
    runtime_status_vocabulary_path.write_text(
        '{"schema_version":"999.0","runtime_status_terms":["running"]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_STATUS_VOCABULARY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-status-vocab-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
