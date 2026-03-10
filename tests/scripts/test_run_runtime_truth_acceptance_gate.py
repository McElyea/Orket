from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.run_runtime_truth_acceptance_gate import (
    REQUIRED_RUNTIME_CONTRACT_FILES,
    evaluate_runtime_truth_acceptance_gate,
    main,
)


def _write_contract_set(workspace: Path, run_id: str) -> Path:
    contracts_dir = workspace / "observability" / run_id / "runtime_contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    for filename in REQUIRED_RUNTIME_CONTRACT_FILES:
        (contracts_dir / filename).write_text(
            json.dumps({"schema_version": "1.0"}, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    return contracts_dir


# Layer: integration
def test_runtime_truth_acceptance_gate_passes_with_drift_and_contract_files(tmp_path: Path) -> None:
    _write_contract_set(tmp_path, "run-ok")
    exit_code = main(["--workspace", str(tmp_path), "--run-id", "run-ok"])
    assert exit_code == 0


# Layer: contract
def test_runtime_truth_acceptance_gate_fails_when_required_contract_file_missing(tmp_path: Path) -> None:
    contracts_dir = _write_contract_set(tmp_path, "run-missing")
    (contracts_dir / REQUIRED_RUNTIME_CONTRACT_FILES[0]).unlink()

    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="run-missing",
        check_drift=False,
    )
    assert payload["ok"] is False
    assert "runtime_contract_files_missing" in payload["failures"]


# Layer: contract
def test_runtime_truth_acceptance_gate_can_run_drift_check_without_run_id(tmp_path: Path) -> None:
    payload = evaluate_runtime_truth_acceptance_gate(
        workspace=tmp_path.resolve(),
        run_id="",
        check_drift=True,
    )
    assert payload["ok"] is True
    assert payload["details"]["drift_report"]["ok"] is True
