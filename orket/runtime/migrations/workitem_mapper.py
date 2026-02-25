from __future__ import annotations

from typing import Any, Dict, Iterable, List


_KIND_MAP = {
    "rock": "initiative",
    "epic": "project",
    "issue": "task",
}


def map_legacy_record(record: Dict[str, Any]) -> Dict[str, Any]:
    legacy_type = str(record.get("type", "issue")).strip().lower()
    kind = _KIND_MAP.get(legacy_type, "task")
    parent_id = record.get("parent_id")
    if legacy_type == "rock":
        parent_id = None
    elif parent_id is None:
        if legacy_type == "epic":
            parent_id = record.get("rock_id")
        elif legacy_type == "issue":
            parent_id = record.get("epic_id")

    mapped: Dict[str, Any] = {
        "id": record.get("id"),
        "kind": kind,
        "parent_id": parent_id,
        "status": record.get("status"),
        "depends_on": list(record.get("depends_on") or []),
        "assignee": record.get("assignee"),
        "requirements_ref": record.get("requirements_ref") or record.get("requirements"),
        "verification_ref": record.get("verification_ref"),
        "metadata": dict(record.get("metadata") or {}),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "legacy": {
            "type": legacy_type,
            "id_alias": record.get("id"),
        },
    }
    for passthrough_key in ("history", "audit", "events"):
        if passthrough_key in record:
            mapped[passthrough_key] = record[passthrough_key]
    return mapped


def map_legacy_records(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [map_legacy_record(record) for record in records]
