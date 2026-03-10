from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_safe_default_catalog_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-safe-default-catalog-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    catalog_path = (
        workspace
        / "observability"
        / "run-safe-default-catalog-immutable"
        / "runtime_contracts"
        / "safe_default_catalog.json"
    )
    catalog_path.write_text(
        '{"schema_version":"999.0","defaults":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_SAFE_DEFAULT_CATALOG_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-safe-default-catalog-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
