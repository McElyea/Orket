from __future__ import annotations

from typing import Any, Protocol

from orket.runtime.registry import protocol_hashing
from orket.runtime.run_ledger_projection import project_run_ledger_record


class _RunLedgerRepository(Protocol):
    async def get_run(self, session_id: str) -> dict[str, Any] | None: ...


def _normalize_run_row(row: dict[str, Any] | None) -> tuple[dict[str, Any] | None, list[str]]:
    projected_row, invalid_projection_fields = project_run_ledger_record(row)
    if projected_row is None:
        return None, []

    normalized = {
        "session_id": str(projected_row.get("session_id") or projected_row.get("id") or ""),
        "run_type": str(projected_row.get("run_type") or ""),
        "run_name": str(projected_row.get("run_name") or ""),
        "department": str(projected_row.get("department") or ""),
        "build_id": str(projected_row.get("build_id") or ""),
        "status": str(projected_row.get("status") or ""),
        "failure_class": projected_row.get("failure_class"),
        "failure_reason": projected_row.get("failure_reason"),
        "summary_json": dict(projected_row.get("summary_json") or {}),
        "artifact_json": dict(projected_row.get("artifact_json") or {}),
    }
    if not normalized["session_id"]:
        normalized["session_id"] = str(projected_row.get("session_id") or "")
    return normalized, invalid_projection_fields


def _field_differences(
    *,
    sqlite_row: dict[str, Any] | None,
    protocol_row: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if sqlite_row is None and protocol_row is None:
        return []
    if sqlite_row is None:
        return [{"field": "__row__", "sqlite": None, "protocol": protocol_row}]
    if protocol_row is None:
        return [{"field": "__row__", "sqlite": sqlite_row, "protocol": None}]

    differences: list[dict[str, Any]] = []
    compared_fields = (
        "session_id",
        "run_type",
        "run_name",
        "department",
        "build_id",
        "status",
        "failure_class",
        "failure_reason",
        "summary_json",
        "artifact_json",
    )
    for field in compared_fields:
        left = sqlite_row.get(field)
        right = protocol_row.get(field)
        if left == right:
            continue
        differences.append({"field": field, "sqlite": left, "protocol": right})
    return differences


async def compare_run_ledger_rows(
    *,
    sqlite_repo: _RunLedgerRepository,
    protocol_repo: _RunLedgerRepository,
    session_id: str,
) -> dict[str, Any]:
    normalized_session_id = str(session_id or "").strip()
    sqlite_raw = await sqlite_repo.get_run(normalized_session_id)
    protocol_raw = await protocol_repo.get_run(normalized_session_id)
    sqlite_row, sqlite_invalid_projection_fields = _normalize_run_row(sqlite_raw)
    protocol_row, protocol_invalid_projection_fields = _normalize_run_row(protocol_raw)
    differences = _field_differences(sqlite_row=sqlite_row, protocol_row=protocol_row)
    if sqlite_invalid_projection_fields or protocol_invalid_projection_fields:
        differences.append(
            {
                "field": "__projection_validation__",
                "sqlite": list(sqlite_invalid_projection_fields),
                "protocol": list(protocol_invalid_projection_fields),
            }
        )

    sqlite_digest = protocol_hashing.hash_canonical_json(sqlite_row) if sqlite_row is not None else None
    protocol_digest = protocol_hashing.hash_canonical_json(protocol_row) if protocol_row is not None else None
    return {
        "session_id": normalized_session_id,
        "parity_ok": len(differences) == 0,
        "differences": differences,
        "sqlite_digest": sqlite_digest,
        "protocol_digest": protocol_digest,
        "sqlite_row": sqlite_row,
        "protocol_row": protocol_row,
        "sqlite_invalid_projection_fields": list(sqlite_invalid_projection_fields),
        "protocol_invalid_projection_fields": list(protocol_invalid_projection_fields),
    }
