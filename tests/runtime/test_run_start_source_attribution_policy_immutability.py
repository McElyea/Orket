from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_source_attribution_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-source-attribution-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 16, 17, 0, 0, tzinfo=UTC),
    )
    policy_path = (
        workspace
        / "observability"
        / "run-source-attribution-policy-immutable"
        / "runtime_contracts"
        / "source_attribution_policy.json"
    )
    policy_path.write_text(
        '{"schema_version":"999.0","modes":[],"required_claim_fields":[],"required_source_fields":[],"failure_reasons":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_SOURCE_ATTRIBUTION_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-source-attribution-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 16, 17, 30, 0, tzinfo=UTC),
        )
