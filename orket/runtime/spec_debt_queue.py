from __future__ import annotations

from typing import Any

from orket.runtime.contract_schema import ContractRegistry

SPEC_DEBT_QUEUE_SCHEMA_VERSION = "1.0"

_ALLOWED_STATUS = {"open", "in_progress", "blocked"}


def spec_debt_queue_snapshot() -> dict[str, Any]:
    return {
        "schema_version": SPEC_DEBT_QUEUE_SCHEMA_VERSION,
        "entries": [
            {
                "debt_id": "SDQ-001",
                "debt_type": "doc_runtime_drift",
                "status": "open",
                "owner": "orket-core",
            },
            {
                "debt_id": "SDQ-002",
                "debt_type": "schema_gap",
                "status": "open",
                "owner": "orket-core",
            },
            {
                "debt_id": "SDQ-003",
                "debt_type": "test_taxonomy_gap",
                "status": "in_progress",
                "owner": "orket-core",
            },
        ],
    }


def validate_spec_debt_queue(payload: dict[str, Any] | None = None) -> tuple[str, ...]:
    queue = dict(payload or spec_debt_queue_snapshot())
    rows = list(queue.get("entries") or [])
    if not rows:
        return ()

    registry = ContractRegistry(
        schema_version=SPEC_DEBT_QUEUE_SCHEMA_VERSION,
        rows=[dict(row) for row in rows if isinstance(row, dict)],
        collection_key="entries",
        row_id_field="debt_id",
        empty_error="E_SPEC_DEBT_QUEUE_EMPTY",
        row_schema_error="E_SPEC_DEBT_QUEUE_ROW_SCHEMA",
        row_id_required_error="E_SPEC_DEBT_QUEUE_DEBT_ID_REQUIRED",
        duplicate_error="E_SPEC_DEBT_QUEUE_DUPLICATE_DEBT_ID",
        required_row_fields=("debt_type", "status", "owner"),
        field_required_errors={
            "debt_type": "E_SPEC_DEBT_QUEUE_DEBT_TYPE_REQUIRED",
            "owner": "E_SPEC_DEBT_QUEUE_OWNER_REQUIRED",
        },
        allowed_row_values={"status": _ALLOWED_STATUS},
        field_allowed_errors={"status": "E_SPEC_DEBT_QUEUE_STATUS_INVALID"},
    )
    debt_ids = list(registry.validate(queue))

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_SPEC_DEBT_QUEUE_ROW_SCHEMA")
    return tuple(sorted(debt_ids))
