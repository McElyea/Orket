from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.runtime.operation_commit_registry import OperationCommitRegistry

from .protocol_append_only_ledger import AppendOnlyRunLedger


class AsyncProtocolRunLedgerRepository:
    """Async wrapper over append-only LPJ-C32 run ledger files."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = asyncio.Lock()

    def _events_path(self, session_id: str) -> Path:
        return self.root / "runs" / str(session_id).strip() / "events.log"

    def _ledger(self, session_id: str) -> AppendOnlyRunLedger:
        return AppendOnlyRunLedger(self._events_path(session_id))

    def _operation_registry(self, session_id: str) -> OperationCommitRegistry:
        return OperationCommitRegistry(self.root / "runs" / str(session_id).strip() / "operation_commits.json")

    def _receipts_path(self, session_id: str) -> Path:
        return self.root / "runs" / str(session_id).strip() / "receipts.log"

    async def start_run(
        self,
        *,
        session_id: str,
        run_type: str,
        run_name: str,
        department: str,
        build_id: str,
        summary: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        event = {
            "kind": "run_started",
            "session_id": session_id,
            "run_type": run_type,
            "run_name": run_name,
            "department": department,
            "build_id": build_id,
            "status": "running",
            "summary": dict(summary or {}),
            "artifacts": dict(artifacts or {}),
        }
        async with self._lock:
            return await asyncio.to_thread(self._ledger(session_id).append_event, event)

    async def finalize_run(
        self,
        *,
        session_id: str,
        status: str,
        failure_class: Optional[str] = None,
        failure_reason: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        event = {
            "kind": "run_finalized",
            "session_id": session_id,
            "status": str(status),
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary": dict(summary or {}),
            "artifacts": dict(artifacts or {}),
        }
        async with self._lock:
            return await asyncio.to_thread(self._ledger(session_id).append_event, event)

    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_kind = str(kind)
        normalized_payload = dict(payload or {})
        event: dict[str, Any] = {
            "kind": normalized_kind,
            "session_id": str(session_id),
        }
        for key, value in normalized_payload.items():
            key_name = str(key).strip()
            if not key_name or key_name in {"kind", "session_id"}:
                continue
            event[key_name] = value
        async with self._lock:
            if normalized_kind in {"operation_result", "tool_result"}:
                operation_id = str(normalized_payload.get("operation_id") or "").strip()
                if operation_id:
                    decision = await self._reserve_operation_commit_locked(
                        session_id=session_id,
                        operation_id=operation_id,
                        kind=normalized_kind,
                        payload=normalized_payload,
                    )
                    if not bool(decision.get("accepted")):
                        return {
                            "kind": "operation_rejected",
                            "session_id": str(session_id),
                            "operation_id": operation_id,
                            "error_code": decision.get("error_code"),
                            "winner_event_seq": decision.get("winner_event_seq"),
                            "winner_entry_digest": decision.get("winner_entry_digest"),
                            "idempotent_reuse": bool(decision.get("idempotent_reuse", False)),
                        }
            return await asyncio.to_thread(self._ledger(session_id).append_event, event)

    async def append_receipt(
        self,
        *,
        session_id: str,
        receipt: Dict[str, Any],
    ) -> dict[str, Any]:
        normalized_session_id = str(session_id or "").strip()
        normalized_receipt = dict(receipt or {})
        async with self._lock:
            return await asyncio.to_thread(
                self._append_receipt_sync,
                normalized_session_id,
                normalized_receipt,
            )

    async def list_receipts(self, session_id: str) -> list[dict[str, Any]]:
        normalized_session_id = str(session_id or "").strip()
        async with self._lock:
            return await asyncio.to_thread(self._load_receipts_sync, normalized_session_id)

    async def list_events(self, session_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            return await asyncio.to_thread(self._ledger(session_id).replay_events)

    async def get_run(self, session_id: str) -> Optional[Dict[str, Any]]:
        events = await self.list_events(session_id)
        if not events:
            return None

        run_type = ""
        run_name = ""
        department = ""
        build_id = ""
        status = "running"
        failure_class: Optional[str] = None
        failure_reason: Optional[str] = None
        summary: Dict[str, Any] = {}
        artifacts: Dict[str, Any] = {}
        started_event_seq = 0
        ended_event_seq = 0

        for event in events:
            kind = str(event.get("kind") or "")
            event_seq = int(event.get("event_seq") or 0)
            if kind == "run_started":
                run_type = str(event.get("run_type") or run_type)
                run_name = str(event.get("run_name") or run_name)
                department = str(event.get("department") or department)
                build_id = str(event.get("build_id") or build_id)
                status = str(event.get("status") or status)
                summary.update(event.get("summary") or {})
                artifacts.update(event.get("artifacts") or {})
                started_event_seq = event_seq
                continue
            if kind == "run_finalized":
                status = str(event.get("status") or status)
                failure_class = event.get("failure_class")
                failure_reason = event.get("failure_reason")
                summary.update(event.get("summary") or {})
                artifacts.update(event.get("artifacts") or {})
                ended_event_seq = event_seq
                continue

        return {
            "session_id": str(session_id),
            "run_type": run_type,
            "run_name": run_name,
            "department": department,
            "build_id": build_id,
            "status": status,
            "failure_class": failure_class,
            "failure_reason": failure_reason,
            "summary_json": summary,
            "artifact_json": artifacts,
            "started_event_seq": started_event_seq,
            "ended_event_seq": ended_event_seq,
        }

    async def _reserve_operation_commit_locked(
        self,
        *,
        session_id: str,
        operation_id: str,
        kind: str,
        payload: Dict[str, Any],
    ) -> dict[str, Any]:
        event_seq = await asyncio.to_thread(self._ledger(session_id).next_event_seq)
        registry = self._operation_registry(session_id)
        entry_digest = hash_canonical_json(
            {
                "kind": str(kind),
                "payload": dict(payload or {}),
            }
        )
        return await asyncio.to_thread(
            registry.commit,
            operation_id=operation_id,
            event_seq=int(event_seq),
            entry_digest=entry_digest,
        )

    def _append_receipt_sync(
        self,
        session_id: str,
        receipt: Dict[str, Any],
    ) -> dict[str, Any]:
        receipts_path = self._receipts_path(session_id)
        existing_rows = self._load_receipts_sync(session_id)
        existing_by_digest = {
            str(row.get("receipt_digest") or ""): dict(row)
            for row in existing_rows
            if str(row.get("receipt_digest") or "").strip()
        }

        last_seq = 0
        for row in existing_rows:
            try:
                seq = int(row.get("receipt_seq") or 0)
            except (TypeError, ValueError):
                seq = 0
            if seq > last_seq:
                last_seq = seq

        normalized = dict(receipt or {})
        receipt_digest = str(normalized.get("receipt_digest") or "").strip()
        if not receipt_digest:
            digest_payload = dict(normalized)
            digest_payload.pop("receipt_digest", None)
            receipt_digest = hash_canonical_json(digest_payload)
            normalized["receipt_digest"] = receipt_digest

        if receipt_digest in existing_by_digest:
            return existing_by_digest[receipt_digest]

        raw_seq = normalized.get("receipt_seq")
        if raw_seq is None:
            normalized["receipt_seq"] = last_seq + 1
        else:
            try:
                normalized["receipt_seq"] = int(raw_seq)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"E_RECEIPT_SEQ_INVALID:{raw_seq}") from exc
            if int(normalized["receipt_seq"]) <= last_seq:
                raise ValueError(
                    f"E_RECEIPT_SEQ_NON_MONOTONIC:{normalized['receipt_seq']}<=last:{last_seq}"
                )

        line = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
        receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        return normalized

    def _load_receipts_sync(self, session_id: str) -> list[dict[str, Any]]:
        receipts_path = self._receipts_path(session_id)
        if not receipts_path.exists():
            return []
        rows: list[dict[str, Any]] = []
        with receipts_path.open("r", encoding="utf-8") as handle:
            for line_index, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"E_RECEIPT_LOG_PARSE:line={line_index}") from exc
                if not isinstance(parsed, dict):
                    raise ValueError(f"E_RECEIPT_LOG_SCHEMA:line={line_index}")
                rows.append(dict(parsed))
        rows.sort(
            key=lambda row: (
                int(row.get("receipt_seq") or 0),
                str(row.get("receipt_digest") or ""),
            )
        )
        return rows
