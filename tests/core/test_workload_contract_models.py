from __future__ import annotations

import pytest

from orket.core.contracts import (
    WORKLOAD_CONTRACT_VERSION_V1,
    WorkloadContractV1,
    missing_required_workload_keys,
    parse_workload_contract,
)


def _valid_payload() -> dict:
    return {
        "workload_contract_version": WORKLOAD_CONTRACT_VERSION_V1,
        "workload_type": "odr",
        "units": [{"unit_id": "pair:qwen:gemma", "mode": "role_matrix"}],
        "required_materials": [{"kind": "file", "value": "scripts/run_odr_live_role_matrix.py"}],
        "expected_artifacts": ["benchmarks/published/ODR/index.json"],
        "validators": ["shape", "trace", "leak"],
        "summary_targets": ["benchmarks/published/ODR/index.json"],
        "provenance_targets": ["benchmarks/published/ODR/provenance.json"],
    }


def test_workload_contract_accepts_valid_payload() -> None:
    model = parse_workload_contract(_valid_payload())
    assert isinstance(model, WorkloadContractV1)
    assert model.workload_type == "odr"


def test_workload_contract_reports_missing_required_keys() -> None:
    payload = _valid_payload()
    del payload["validators"]
    del payload["summary_targets"]
    missing = missing_required_workload_keys(payload)
    assert missing == ["summary_targets", "validators"]
    with pytest.raises(ValueError, match="missing required workload contract keys"):
        parse_workload_contract(payload)


def test_workload_contract_rejects_unknown_contract_version() -> None:
    payload = _valid_payload()
    payload["workload_contract_version"] = "workload.contract.v0"
    with pytest.raises(ValueError, match="unsupported workload_contract_version"):
        parse_workload_contract(payload)


def test_workload_contract_rejects_extra_fields() -> None:
    payload = _valid_payload()
    payload["legacy_fallback"] = True
    with pytest.raises(ValueError):
        WorkloadContractV1.model_validate(payload)
