from __future__ import annotations

import pytest

from orket.runtime.runtime_truth_trace_ids import (
    resolve_runtime_truth_trace_id,
    runtime_truth_trace_ids_snapshot,
)


# Layer: unit
def test_runtime_truth_trace_ids_snapshot_contains_expected_rows() -> None:
    payload = runtime_truth_trace_ids_snapshot()
    assert payload["schema_version"] == "1.0"
    artifacts = {row["artifact"] for row in payload["trace_ids"]}
    assert "run_phase_contract" in artifacts
    assert "runtime_truth_contract_drift_report" in artifacts
    assert "clock_time_authority_policy" in artifacts
    assert "capability_fallback_hierarchy" in artifacts
    assert "model_profile_bios" in artifacts
    assert "route_decision_artifact" in artifacts


# Layer: contract
def test_resolve_runtime_truth_trace_id_returns_registered_id() -> None:
    assert resolve_runtime_truth_trace_id("run_phase_contract") == "TRUTH-A-RUN-PHASE-CONTRACT"


# Layer: contract
def test_resolve_runtime_truth_trace_id_rejects_unknown_artifact() -> None:
    with pytest.raises(ValueError, match="E_RUNTIME_TRUTH_TRACE_ID_UNKNOWN:unknown_artifact"):
        _ = resolve_runtime_truth_trace_id("unknown_artifact")
