"""Real, isolated repository inputs for runtime-truth governance contract tests."""
import json
from pathlib import Path

import pytest

import orket
from orket.runtime.decision_record_operating_principles_contract import (
    decision_record_operating_principles_contract_snapshot,
)
from orket.runtime.retry_classification_policy import retry_classification_policy_snapshot
from orket.runtime.runtime_boundary_audit_checklist import runtime_boundary_audit_checklist_snapshot
from scripts.governance import run_runtime_truth_acceptance_gate as gate


@pytest.fixture
def runtime_truth_repository_inputs(tmp_path, monkeypatch):
    """Copy actual inputs without putting copied core sources on the import path."""
    repository = Path(__file__).resolve().parents[2]
    package = Path(orket.__file__).resolve().parent
    workspace = tmp_path / "governance-repository-inputs"
    boundaries = runtime_boundary_audit_checklist_snapshot()["boundaries"]
    documents = decision_record_operating_principles_contract_snapshot()["checks"]
    names = {row["path"] for row in boundaries} | {row["relative_path"] for row in documents}
    for name in sorted(names):
        relative = Path(name)
        source = package.joinpath(*relative.parts[1:]) if relative.parts[0] == "orket" else repository / relative
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
    monkeypatch.setattr(gate, "REPO_ROOT", workspace)


def write_contract_set(workspace: Path, run_id: str) -> Path:
    contracts_dir = workspace / "observability" / run_id / "runtime_contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    for filename in gate.REQUIRED_RUNTIME_CONTRACT_FILES:
        payload = {"schema_version": "1.0"}
        if filename == "retry_classification_policy.json":
            payload = retry_classification_policy_snapshot()
        (contracts_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=True) + "\n", encoding="utf-8",
        )
    return contracts_dir
