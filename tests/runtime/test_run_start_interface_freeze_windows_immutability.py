from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_interface_freeze_windows_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-interface-freeze-windows-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    freeze_windows_path = (
        workspace
        / "observability"
        / "run-interface-freeze-windows-immutable"
        / "runtime_contracts"
        / "interface_freeze_windows.json"
    )
    freeze_windows_path.write_text(
        '{"schema_version":"999.0","windows":[],"emergency_break_policy":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_INTERFACE_FREEZE_WINDOWS_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-interface-freeze-windows-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
