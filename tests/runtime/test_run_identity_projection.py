from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


def _run_identity_path(*, workspace: Path, run_id: str) -> Path:
    return workspace / "observability" / run_id / "runtime_contracts" / "run_identity.json"


# Layer: contract
@pytest.mark.parametrize(
    ("field_name", "field_value", "expected_error"),
    [
        ("identity_scope", "invocation_scope", "E_RUN_IDENTITY_SCHEMA:identity_scope_invalid"),
        ("projection_source", "legacy_bootstrap", "E_RUN_IDENTITY_SCHEMA:projection_source_invalid"),
        ("projection_only", False, "E_RUN_IDENTITY_SCHEMA:projection_only_invalid"),
    ],
)
def test_capture_run_start_artifacts_rejects_drifted_run_identity_projection(
    tmp_path: Path,
    field_name: str,
    field_value: str | bool,
    expected_error: str,
) -> None:
    workspace = tmp_path / "workspace"
    artifact = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-identity-projection",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    run_identity = dict(artifact["run_identity"])
    run_identity[field_name] = field_value
    path = _run_identity_path(workspace=workspace, run_id="run-identity-projection")
    path.write_text(json.dumps(run_identity, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match=expected_error):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-identity-projection",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
