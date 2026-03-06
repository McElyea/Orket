from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

from orket.adapters.storage.protocol_append_only_ledger import AppendOnlyRunLedger
from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.runtime.contract_bootstrap import load_runtime_contract_snapshots


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def artifact_digest_inventory(artifact_root: Path) -> list[dict[str, Any]]:
    if not artifact_root.exists():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(artifact_root.rglob("*"), key=lambda entry: entry.as_posix()):
        if not path.is_file():
            continue
        rel = str(path.relative_to(artifact_root)).replace("\\", "/")
        rows.append(
            {
                "path": rel,
                "sha256": _sha256_file(path),
                "size_bytes": int(path.stat().st_size),
            }
        )
    return rows


def receipt_digest_inventory(receipts_log_path: Path) -> list[dict[str, Any]]:
    if not receipts_log_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with receipts_log_path.open("r", encoding="utf-8") as handle:
        for line_index, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "receipt_seq": int(payload.get("receipt_seq") or 0),
                    "receipt_digest": str(payload.get("receipt_digest") or ""),
                    "event_seq_range": list(payload.get("event_seq_range") or []),
                    "operation_id": str(payload.get("operation_id") or ""),
                    "execution_capsule": _receipt_execution_capsule(payload),
                    "line": int(line_index),
                }
            )
    rows.sort(
        key=lambda row: (
            int(row.get("receipt_seq") or 0),
            str(row.get("receipt_digest") or ""),
            str(row.get("operation_id") or ""),
        )
    )
    return rows


def _receipt_execution_capsule(receipt_payload: dict[str, Any]) -> dict[str, Any]:
    capsule = receipt_payload.get("execution_capsule")
    if not isinstance(capsule, dict):
        return {}
    return {
        "network_mode": str(capsule.get("network_mode") or ""),
        "network_allowlist_hash": str(capsule.get("network_allowlist_hash") or ""),
        "clock_mode": str(capsule.get("clock_mode") or ""),
        "clock_artifact_ref": str(capsule.get("clock_artifact_ref") or ""),
        "clock_artifact_hash": str(capsule.get("clock_artifact_hash") or ""),
        "timezone": str(capsule.get("timezone") or ""),
        "locale": str(capsule.get("locale") or ""),
        "env_allowlist_hash": str(capsule.get("env_allowlist_hash") or ""),
    }


def runtime_contract_versions_snapshot() -> dict[str, Any]:
    snapshots = load_runtime_contract_snapshots()
    return {
        "tool_registry_version": snapshots.tool_registry_snapshot.get("tool_registry_version"),
        "artifact_schema_registry_version": snapshots.artifact_schema_snapshot.get("artifact_schema_registry_version"),
        "compatibility_map_schema_version": snapshots.compatibility_map_schema_snapshot.get("schema_version"),
        "tool_registry_snapshot_hash": snapshots.tool_registry_snapshot.get("snapshot_hash"),
        "artifact_schema_snapshot_hash": snapshots.artifact_schema_snapshot.get("snapshot_hash"),
        "tool_contract_snapshot_hash": snapshots.tool_contract_snapshot.get("snapshot_hash"),
    }


class ProtocolReplayEngine:
    """Reconstruct protocol-governed run state from append-only ledger + artifacts."""

    def replay_from_ledger(
        self,
        *,
        events_log_path: Path,
        artifact_root: Path | None = None,
        receipts_log_path: Path | None = None,
    ) -> dict[str, Any]:
        ledger = AppendOnlyRunLedger(events_log_path)
        events = ledger.replay_events()
        resolved_receipts_path = receipts_log_path
        if resolved_receipts_path is None:
            candidate = events_log_path.with_name("receipts.log")
            resolved_receipts_path = candidate if candidate.exists() else None
        receipts = (
            receipt_digest_inventory(resolved_receipts_path)
            if resolved_receipts_path is not None
            else []
        )

        summary: dict[str, Any] = {
            "session_id": "",
            "run_type": "",
            "run_name": "",
            "department": "",
            "build_id": "",
            "status": "running",
            "failure_class": None,
            "failure_reason": None,
            "event_count": len(events),
            "last_event_seq": 0,
            "operations": {},
            "status_timeline": [],
            "artifact_inventory": artifact_digest_inventory(artifact_root) if artifact_root else [],
            "receipt_inventory": receipts,
            "runtime_contract_snapshots": runtime_contract_versions_snapshot(),
        }

        for event in events:
            event_seq = int(event.get("event_seq") or 0)
            kind = str(event.get("kind") or "")
            if event_seq > summary["last_event_seq"]:
                summary["last_event_seq"] = event_seq

            session_id = str(event.get("session_id") or "")
            if session_id and not summary["session_id"]:
                summary["session_id"] = session_id

            if kind == "run_started":
                summary["run_type"] = str(event.get("run_type") or summary["run_type"])
                summary["run_name"] = str(event.get("run_name") or summary["run_name"])
                summary["department"] = str(event.get("department") or summary["department"])
                summary["build_id"] = str(event.get("build_id") or summary["build_id"])
                status = str(event.get("status") or summary["status"])
                summary["status"] = status
                summary["status_timeline"].append({"event_seq": event_seq, "status": status})
                continue

            if kind == "run_finalized":
                status = str(event.get("status") or summary["status"])
                summary["status"] = status
                summary["failure_class"] = event.get("failure_class")
                summary["failure_reason"] = event.get("failure_reason")
                summary["status_timeline"].append({"event_seq": event_seq, "status": status})
                continue

            if kind in {"tool_result", "operation_result"}:
                operation_id = str(event.get("operation_id") or "")
                if not operation_id:
                    continue
                summary["operations"][operation_id] = {
                    "event_seq": event_seq,
                    "tool": str(event.get("tool") or ""),
                    "ok": bool((event.get("result") or {}).get("ok")) if isinstance(event.get("result"), dict) else None,
                }

        summary["operation_count"] = len(summary["operations"])
        summary["receipt_count"] = len(summary["receipt_inventory"])
        summary["state_digest"] = hash_canonical_json(
            {
                "session_id": summary["session_id"],
                "run_type": summary["run_type"],
                "run_name": summary["run_name"],
                "department": summary["department"],
                "build_id": summary["build_id"],
                "status": summary["status"],
                "failure_class": summary["failure_class"],
                "failure_reason": summary["failure_reason"],
                "last_event_seq": summary["last_event_seq"],
                "operations": summary["operations"],
                "artifact_inventory": summary["artifact_inventory"],
                "receipt_inventory": summary["receipt_inventory"],
                "runtime_contract_snapshots": summary["runtime_contract_snapshots"],
            }
        )
        return summary

    def compare_replays(
        self,
        *,
        run_a_events_path: Path,
        run_b_events_path: Path,
        run_a_artifact_root: Path | None = None,
        run_b_artifact_root: Path | None = None,
        run_a_receipts_path: Path | None = None,
        run_b_receipts_path: Path | None = None,
    ) -> dict[str, Any]:
        replay_a = self.replay_from_ledger(
            events_log_path=run_a_events_path,
            artifact_root=run_a_artifact_root,
            receipts_log_path=run_a_receipts_path,
        )
        replay_b = self.replay_from_ledger(
            events_log_path=run_b_events_path,
            artifact_root=run_b_artifact_root,
            receipts_log_path=run_b_receipts_path,
        )

        differences: list[dict[str, Any]] = []
        self._maybe_add_difference(differences, "status", replay_a["status"], replay_b["status"])
        self._maybe_add_difference(differences, "failure_class", replay_a["failure_class"], replay_b["failure_class"])
        self._maybe_add_difference(differences, "failure_reason", replay_a["failure_reason"], replay_b["failure_reason"])
        self._maybe_add_difference(differences, "last_event_seq", replay_a["last_event_seq"], replay_b["last_event_seq"])
        self._maybe_add_difference(differences, "operations", replay_a["operations"], replay_b["operations"])
        self._maybe_add_difference(
            differences,
            "artifact_inventory",
            replay_a["artifact_inventory"],
            replay_b["artifact_inventory"],
        )
        self._maybe_add_difference(
            differences,
            "receipt_inventory",
            replay_a["receipt_inventory"],
            replay_b["receipt_inventory"],
        )

        deterministic_match = replay_a["state_digest"] == replay_b["state_digest"]
        return {
            "deterministic_match": deterministic_match and not differences,
            "state_digest_a": replay_a["state_digest"],
            "state_digest_b": replay_b["state_digest"],
            "differences": differences,
            "run_a": replay_a,
            "run_b": replay_b,
        }

    @staticmethod
    def _maybe_add_difference(
        differences: list[dict[str, Any]],
        field: str,
        value_a: Any,
        value_b: Any,
    ) -> None:
        if value_a == value_b:
            return
        differences.append(
            {
                "field": str(field),
                "a": value_a,
                "b": value_b,
            }
        )
