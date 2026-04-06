from __future__ import annotations

from typing import Any

CANONICAL_EXAMPLES_LIBRARY_SCHEMA_VERSION = "1.0"

_EXPECTED_EXAMPLE_IDS = {
    "EX-ROUTE-DECISION-BASELINE",
    "EX-REPAIR-LEDGER-BASELINE",
    "EX-DEGRADATION-LABELING-BASELINE",
    "EX-OPERATOR-OVERRIDE-BASELINE",
}


def canonical_examples_library_snapshot() -> dict[str, Any]:
    return {
        "schema_version": CANONICAL_EXAMPLES_LIBRARY_SCHEMA_VERSION,
        "examples": [
            {
                "example_id": "EX-ROUTE-DECISION-BASELINE",
                "artifact_type": "route_decision_artifact",
                "status": "canonical",
            },
            {
                "example_id": "EX-REPAIR-LEDGER-BASELINE",
                "artifact_type": "repair_ledger",
                "status": "canonical",
            },
            {
                "example_id": "EX-DEGRADATION-LABELING-BASELINE",
                "artifact_type": "degradation_labeling",
                "status": "canonical",
            },
            {
                "example_id": "EX-OPERATOR-OVERRIDE-BASELINE",
                "artifact_type": "operator_override_log",
                "status": "canonical",
            },
        ],
    }


def validate_canonical_examples_library(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    library = dict(payload or canonical_examples_library_snapshot())
    rows = list(library.get("examples") or [])
    if not rows:
        raise ValueError("E_CANONICAL_EXAMPLES_LIBRARY_EMPTY")

    observed_ids: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_CANONICAL_EXAMPLES_LIBRARY_ROW_SCHEMA")
        example_id = str(row.get("example_id") or "").strip()
        artifact_type = str(row.get("artifact_type") or "").strip()
        status = str(row.get("status") or "").strip()
        if not example_id:
            raise ValueError("E_CANONICAL_EXAMPLES_LIBRARY_ID_REQUIRED")
        if not artifact_type:
            raise ValueError(f"E_CANONICAL_EXAMPLES_LIBRARY_ARTIFACT_TYPE_REQUIRED:{example_id}")
        if status != "canonical":
            raise ValueError(f"E_CANONICAL_EXAMPLES_LIBRARY_STATUS_INVALID:{example_id}")
        observed_ids.append(example_id)

    if len(set(observed_ids)) != len(observed_ids):
        raise ValueError("E_CANONICAL_EXAMPLES_LIBRARY_DUPLICATE_ID")
    if {token for token in observed_ids} != _EXPECTED_EXAMPLE_IDS:
        raise ValueError("E_CANONICAL_EXAMPLES_LIBRARY_ID_SET_MISMATCH")
    return tuple(sorted(observed_ids))
