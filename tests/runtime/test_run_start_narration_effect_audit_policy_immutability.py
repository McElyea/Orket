from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_narration_effect_audit_policy_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-narration-effect-audit-policy-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 16, 17, 0, 0, tzinfo=UTC),
    )
    policy_path = (
        workspace
        / "observability"
        / "run-narration-effect-audit-policy-immutable"
        / "runtime_contracts"
        / "narration_effect_audit_policy.json"
    )
    policy_path.write_text('{"schema_version":"999.0","audit_statuses":[],"failure_reasons":[],"rows":[]}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="E_RUN_NARRATION_EFFECT_AUDIT_POLICY_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-narration-effect-audit-policy-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 16, 17, 30, 0, tzinfo=UTC),
        )
