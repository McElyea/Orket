from __future__ import annotations

import pytest

from orket.runtime.runtime_truth_contracts import (
    degradation_taxonomy_snapshot,
    fail_behavior_registry_snapshot,
    runtime_status_vocabulary_snapshot,
    validate_runtime_status,
)


# Layer: unit
def test_runtime_status_vocabulary_snapshot_has_expected_terms() -> None:
    payload = runtime_status_vocabulary_snapshot()
    assert payload["schema_version"] == "1.0"
    assert payload["runtime_status_terms"] == [
        "running",
        "done",
        "failed",
        "terminal_failure",
        "incomplete",
        "blocked",
        "degraded",
    ]


# Layer: contract
def test_validate_runtime_status_accepts_registered_token() -> None:
    assert validate_runtime_status("TERMINAL_FAILURE") == "terminal_failure"


# Layer: contract
def test_validate_runtime_status_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="E_RUNTIME_STATUS_UNKNOWN:unknown"):
        _ = validate_runtime_status("unknown")


# Layer: contract
def test_degradation_taxonomy_snapshot_has_required_levels() -> None:
    payload = degradation_taxonomy_snapshot()
    assert payload["schema_version"] == "1.0"
    levels = {row["level"] for row in payload["levels"]}
    assert levels == {"none", "degraded", "blocked"}


# Layer: contract
def test_fail_behavior_registry_snapshot_contains_fail_open_and_fail_closed() -> None:
    payload = fail_behavior_registry_snapshot()
    assert payload["schema_version"] == "1.0"
    modes = {row["failure_mode"] for row in payload["subsystems"]}
    assert modes == {"fail_open", "fail_closed"}
