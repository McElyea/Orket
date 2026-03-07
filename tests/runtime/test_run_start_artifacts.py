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
    assert Path(payload["run_identity_path"]).exists()
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
