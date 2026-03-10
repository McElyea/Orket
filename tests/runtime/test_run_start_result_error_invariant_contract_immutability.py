from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_result_error_invariant_contract_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-result-error-invariant-contract-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    contract_path = (
        workspace
        / "observability"
        / "run-result-error-invariant-contract-immutable"
        / "runtime_contracts"
        / "result_error_invariant_contract.json"
    )
    contract_path.write_text(
        '{"schema_version":"999.0","failure_forbidden_statuses":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_RESULT_ERROR_INVARIANT_CONTRACT_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-result-error-invariant-contract-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
