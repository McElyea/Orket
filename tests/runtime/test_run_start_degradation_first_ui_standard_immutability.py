from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_degradation_first_ui_standard_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-degradation-first-ui-standard-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    contract_path = (
        workspace
        / "observability"
        / "run-degradation-first-ui-standard-immutable"
        / "runtime_contracts"
        / "degradation_first_ui_standard.json"
    )
    contract_path.write_text(
        '{"schema_version":"999.0","checks":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_DEGRADATION_FIRST_UI_STANDARD_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-degradation-first-ui-standard-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
