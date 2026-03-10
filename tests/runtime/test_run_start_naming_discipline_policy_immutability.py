from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_naming_discipline_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-naming-discipline-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    policy_path = (
        workspace
        / "observability"
        / "run-naming-discipline-policy-immutable"
        / "runtime_contracts"
        / "naming_discipline_policy.json"
    )
    policy_path.write_text(
        '{"schema_version":"999.0","conventions":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_NAMING_DISCIPLINE_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-naming-discipline-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
