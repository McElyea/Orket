from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_non_fatal_error_budget_mutation(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-non-fatal-error-budget-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    budget_path = (
        workspace
        / "observability"
        / "run-non-fatal-error-budget-immutable"
        / "runtime_contracts"
        / "non_fatal_error_budget.json"
    )
    budget_path.write_text(
        '{"schema_version":"999.0","evaluation_window":{},"budgets":[],"escalation_policy":{}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_NON_FATAL_ERROR_BUDGET_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-non-fatal-error-budget-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
