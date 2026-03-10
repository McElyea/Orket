from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.runtime.run_start_artifacts import capture_run_start_artifacts


# Layer: contract
def test_capture_run_start_artifacts_fails_closed_on_cold_start_truth_test_contract_mutation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    _ = capture_run_start_artifacts(
        workspace=workspace,
        run_id="run-cold-start-truth-test-contract-immutable",
        workload="core_epic",
        now=datetime(2026, 3, 6, 17, 0, 0, tzinfo=UTC),
    )
    contract_path = (
        workspace
        / "observability"
        / "run-cold-start-truth-test-contract-immutable"
        / "runtime_contracts"
        / "cold_start_truth_test_contract.json"
    )
    contract_path.write_text(
        '{"schema_version":"999.0","checks":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="E_RUN_COLD_START_TRUTH_TEST_CONTRACT_IMMUTABLE"):
        _ = capture_run_start_artifacts(
            workspace=workspace,
            run_id="run-cold-start-truth-test-contract-immutable",
            workload="core_epic",
            now=datetime(2026, 3, 6, 17, 30, 0, tzinfo=UTC),
        )
