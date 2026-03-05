from __future__ import annotations

from typing import Any, Protocol

from orket.application.workflows.protocol_hashing import hash_canonical_json


class _RunLedgerRepository(Protocol):
    async def get_run(self, session_id: str) -> dict[str, Any] | None: ...


def _normalize_summary(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return {}
    return {}


def _normalize_artifacts(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        return {}
    return {}


def _normalize_run_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None

    # SQLite repository shape uses summary_json/artifact_json.
    summary_json = row.get("summary_json")
    artifact_json = row.get("artifact_json")

    normalized = {
        "session_id": str(row.get("session_id") or row.get("id") or ""),
        "run_type": str(row.get("run_type") or ""),
        "run_name": str(row.get("run_name") or ""),
        "department": str(row.get("department") or ""),
        "build_id": str(row.get("build_id") or ""),
        "status": str(row.get("status") or ""),
        "failure_class": row.get("failure_class"),
        "failure_reason": row.get("failure_reason"),
        "summary_json": _normalize_summary(summary_json),
        "artifact_json": _normalize_artifacts(artifact_json),
    }
    if not normalized["session_id"]:
        normalized["session_id"] = str(row.get("session_id") or "")
    return normalized


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
    sqlite_row = _normalize_run_row(sqlite_raw)
    protocol_row = _normalize_run_row(protocol_raw)
    differences = _field_differences(sqlite_row=sqlite_row, protocol_row=protocol_row)

    sqlite_digest = hash_canonical_json(sqlite_row) if sqlite_row is not None else None
    protocol_digest = hash_canonical_json(protocol_row) if protocol_row is not None else None
    return {
        "session_id": normalized_session_id,
        "parity_ok": len(differences) == 0,
        "differences": differences,
        "sqlite_digest": sqlite_digest,
        "protocol_digest": protocol_digest,
        "sqlite_row": sqlite_row,
        "protocol_row": protocol_row,
    }
