from __future__ import annotations

import pytest

from orket.runtime.run_phase_contract import (
    CANONICAL_RUN_PHASE_ORDER,
    run_phase_contract_snapshot,
    validate_phase_trace,
)


# Layer: unit
def test_run_phase_contract_snapshot_matches_canonical_order() -> None:
    payload = run_phase_contract_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["entry_phase"] == CANONICAL_RUN_PHASE_ORDER[0]
    assert payload["terminal_phase"] == CANONICAL_RUN_PHASE_ORDER[-1]
    assert payload["canonical_phase_order"] == list(CANONICAL_RUN_PHASE_ORDER)


# Layer: contract
def test_validate_phase_trace_accepts_monotonic_progression() -> None:
    validated = validate_phase_trace(
        [
            "input_normalize",
            "route",
            "execute",
            "execute",
            "finalize",
            "persist",
            "emit_observability",
        ]
    )
    assert validated[-1] == "emit_observability"


# Layer: contract
def test_validate_phase_trace_rejects_unknown_phase_token() -> None:
    with pytest.raises(ValueError, match="E_RUN_PHASE_UNKNOWN:render_output"):
        _ = validate_phase_trace(["input_normalize", "render_output"])


# Layer: contract
def test_validate_phase_trace_rejects_non_monotonic_regression() -> None:
    with pytest.raises(ValueError, match="E_RUN_PHASE_ORDER:execute->route"):
        _ = validate_phase_trace(["input_normalize", "route", "execute", "route"])


# Layer: contract
def test_validate_phase_trace_requires_non_empty_trace() -> None:
    with pytest.raises(ValueError, match="E_RUN_PHASE_TRACE_REQUIRED"):
        _ = validate_phase_trace([])
