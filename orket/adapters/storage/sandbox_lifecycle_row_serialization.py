from __future__ import annotations

import json

from orket.core.domain.sandbox_lifecycle_records import SandboxOperationDedupeEntry


def deserialize_record_row(row: dict[str, object]) -> dict[str, object]:
    row["managed_resource_inventory"] = json.loads(str(row.pop("managed_resource_inventory_json")))
    row["requires_reconciliation"] = bool(row["requires_reconciliation"])
    return row


def deserialize_operation_row(row: dict[str, object]) -> SandboxOperationDedupeEntry:
    return SandboxOperationDedupeEntry.model_validate(
        {
            "operation_id": row["operation_id"],
            "payload_hash": row["payload_hash"],
            "result_payload": json.loads(str(row["result_payload_json"])),
            "created_at": row["created_at"],
        }
    )


def deserialize_event_row(row: dict[str, object]) -> dict[str, object]:
    row["payload"] = json.loads(str(row.pop("payload_json")))
    return row
