from __future__ import annotations

from typing import Any

SPEC_DEBT_QUEUE_SCHEMA_VERSION = "1.0"

_ALLOWED_STATUS = {"open", "in_progress", "blocked"}
_EXPECTED_DEBT_TYPES = {"doc_runtime_drift", "schema_gap", "test_taxonomy_gap"}


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
        raise ValueError("E_SPEC_DEBT_QUEUE_EMPTY")

    debt_ids: list[str] = []
    debt_types: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("E_SPEC_DEBT_QUEUE_ROW_SCHEMA")
        debt_id = str(row.get("debt_id") or "").strip()
        debt_type = str(row.get("debt_type") or "").strip()
        status = str(row.get("status") or "").strip().lower()
        owner = str(row.get("owner") or "").strip()
        if not debt_id:
            raise ValueError("E_SPEC_DEBT_QUEUE_DEBT_ID_REQUIRED")
        if debt_type not in _EXPECTED_DEBT_TYPES:
            raise ValueError(f"E_SPEC_DEBT_QUEUE_DEBT_TYPE_INVALID:{debt_id}")
        if status not in _ALLOWED_STATUS:
            raise ValueError(f"E_SPEC_DEBT_QUEUE_STATUS_INVALID:{debt_id}")
        if not owner:
            raise ValueError(f"E_SPEC_DEBT_QUEUE_OWNER_REQUIRED:{debt_id}")
        debt_ids.append(debt_id)
        debt_types.add(debt_type)

    if len(set(debt_ids)) != len(debt_ids):
        raise ValueError("E_SPEC_DEBT_QUEUE_DUPLICATE_DEBT_ID")
    if debt_types != _EXPECTED_DEBT_TYPES:
        raise ValueError("E_SPEC_DEBT_QUEUE_DEBT_TYPE_SET_MISMATCH")
    return tuple(sorted(debt_ids))
