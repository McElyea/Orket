from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_runtime_boundary_audit_checklist_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-runtime-boundary-audit-checklist-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    checklist_path = (
        workspace
        / "observability"
        / "run-runtime-boundary-audit-checklist-immutable"
        / "runtime_contracts"
        / "runtime_boundary_audit_checklist.json"
    )
    checklist_path.write_text(
        '{"schema_version":"999.0","boundaries":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_RUNTIME_BOUNDARY_AUDIT_CHECKLIST_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-runtime-boundary-audit-checklist-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
