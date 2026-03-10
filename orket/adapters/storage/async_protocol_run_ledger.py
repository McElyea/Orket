from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from orket.application.workflows.protocol_hashing import hash_canonical_json
from orket.application.workflows.tool_invocation_contracts import (
    compute_tool_call_hash,
    normalize_tool_invocation_manifest,
)
from orket.runtime.operation_commit_registry import OperationCommitRegistry
from orket.runtime.protocol_error_codes import (
    E_RECEIPT_LOG_PARSE_PREFIX,
    E_RECEIPT_LOG_SCHEMA_PREFIX,
    E_RECEIPT_SEQ_INVALID_PREFIX,
    E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX,
)
from orket.runtime.result_error_invariants import validate_result_error_invariant
from orket.runtime.run_graph_reconstruction import (
    reconstruct_run_graph,
    write_run_graph_artifact,
)

from .protocol_append_only_ledger import AppendOnlyRunLedger

_TOOL_INVOCATION_KINDS = {"tool_call", "operation_result", "tool_result"}
_TOOL_RESULT_KINDS = {"operation_result", "tool_result"}


class AsyncProtocolRunLedgerRepository:
    """Async wrapper over append-only LPJ-C32 run ledger files."""

    def __init__(self, root: str | Path, *, max_tool_invocations_per_run: int = 200) -> None:
        self.root = Path(root)
        self._lock = asyncio.Lock()
        self.max_tool_invocations_per_run = max(int(max_tool_invocations_per_run), 1)

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
        event = self._build_event(
            session_id=session_id,
            kind="run_started",
            event_type="run_started",
            run_type=run_type,
            run_name=run_name,
            department=department,
            build_id=build_id,
            status="running",
            summary=dict(summary or {}),
            artifacts=dict(artifacts or {}),
        )
        async with self._lock:
            return await self._append_event_locked(session_id=session_id, event=event)

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
        resolved_status = validate_result_error_invariant(
            status=status,
            failure_class=failure_class,
            failure_reason=failure_reason,
        )
        event = self._build_event(
            session_id=session_id,
            kind="run_finalized",
            event_type="run_finalized",
            status=str(resolved_status),
            failure_class=failure_class,
            failure_reason=failure_reason,
            summary=dict(summary or {}),
            artifacts=dict(artifacts or {}),
        )
        async with self._lock:
            existing_events = await asyncio.to_thread(self._ledger(session_id).replay_events)
            rejection = self._validate_ordering_contract(
                session_id=session_id,
                kind="run_finalized",
                payload={},
                event=event,
                existing_events=existing_events,
            )
            if rejection is not None:
                raise ValueError(str(rejection.get("error_code") or "E_LEDGER_CALL_RESULT_ORDER"))
            next_seq = 1
            if existing_events:
                next_seq = max(self._event_sequence(row) for row in existing_events) + 1
            pending_events = [dict(row) for row in existing_events]
            pending_finalized_event = dict(event)
            pending_finalized_event["event_seq"] = int(next_seq)
            pending_finalized_event["sequence_number"] = int(next_seq)
            pending_events.append(pending_finalized_event)
            run_graph_payload = await asyncio.to_thread(
                reconstruct_run_graph,
                pending_events,
                session_id=str(session_id),
            )
            await asyncio.to_thread(
                write_run_graph_artifact,
                root=self.root,
                session_id=str(session_id),
                payload=run_graph_payload,
            )
            return await self._append_event_locked(
                session_id=session_id,
                event=event,
                existing_events=existing_events,
            )

    async def append_event(
        self,
        *,
        session_id: str,
        kind: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> dict[str, Any]:
        normalized_kind = str(kind)
        normalized_payload = dict(payload or {})
        event: dict[str, Any] = self._build_event(
            session_id=session_id,
            kind=normalized_kind,
            event_type=normalized_kind,
        )
        protected_fields = {
            "kind",
            "session_id",
            "run_id",
            "ledger_schema_version",
            "event_type",
            "sequence_number",
            "event_seq",
            "timestamp",
        }
        for key, value in normalized_payload.items():
            key_name = str(key).strip()
            if not key_name or key_name in protected_fields:
                continue
            event[key_name] = value
        if (not str(event.get("tool_name") or "").strip()) and "tool" in event:
            event["tool_name"] = str(event.get("tool") or "")
        if normalized_kind in _TOOL_INVOCATION_KINDS:
            manifest = self._resolve_tool_invocation_manifest(
                session_id=str(session_id),
                payload=normalized_payload,
                event=event,
            )
            if manifest is None:
                return {
                    "kind": "tool_invocation_rejected",
                    "session_id": str(session_id),
                    "run_id": str(session_id),
                    "error_code": "E_TOOL_INVOCATION_MANIFEST_INVALID",
                }
            event["tool_invocation_manifest"] = manifest
            event["tool_name"] = str(manifest.get("tool_name") or "")
            if normalized_kind == "tool_call":
                raw_tool_args = normalized_payload.get("tool_args")
                if not isinstance(raw_tool_args, dict):
                    raw_tool_args = normalized_payload.get("args")
                tool_args = dict(raw_tool_args) if isinstance(raw_tool_args, dict) else {}
                event["tool_args"] = tool_args
                event["tool_call_hash"] = compute_tool_call_hash(
                    tool_name=str(manifest.get("tool_name") or ""),
                    tool_args=tool_args,
                    tool_contract_version=str(manifest.get("tool_contract_version") or ""),
                    capability_profile=str(manifest.get("capability_profile") or ""),
                )
            else:
                tool_call_hash = str(normalized_payload.get("tool_call_hash") or "").strip()
                if tool_call_hash:
                    event["tool_call_hash"] = tool_call_hash
        async with self._lock:
            existing_events = await asyncio.to_thread(self._ledger(session_id).replay_events)
            if normalized_kind in _TOOL_INVOCATION_KINDS:
                invocation_count = self._tool_invocation_count(existing_events)
                if invocation_count >= self.max_tool_invocations_per_run:
                    return {
                        "kind": "tool_invocation_rejected",
                        "session_id": str(session_id),
                        "run_id": str(session_id),
                        "error_code": "E_MAX_TOOL_INVOCATIONS_EXCEEDED",
                        "max_tool_invocations_per_run": int(self.max_tool_invocations_per_run),
                        "invocation_count": int(invocation_count),
                    }
            if normalized_kind in _TOOL_RESULT_KINDS:
                operation_id = str(normalized_payload.get("operation_id") or "").strip()
                if operation_id:
                    duplicate = await self._duplicate_operation_rejection_locked(
                        session_id=session_id,
                        operation_id=operation_id,
                        kind=normalized_kind,
                        payload=normalized_payload,
                    )
                    if duplicate is not None:
                        return duplicate
            rejection = self._validate_ordering_contract(
                session_id=session_id,
                kind=normalized_kind,
                payload=normalized_payload,
                event=event,
                existing_events=existing_events,
            )
            if rejection is not None:
                return rejection
            if normalized_kind == "tool_call":
                operation_id = str(normalized_payload.get("operation_id") or "").strip()
                if operation_id:
                    winner = await asyncio.to_thread(self._operation_registry(str(session_id)).winner, operation_id)
                    if winner is not None:
                        return {
                            "kind": "operation_rejected",
                            "session_id": str(session_id),
                            "operation_id": operation_id,
                            "error_code": "E_DUPLICATE_OPERATION",
                            "winner_event_seq": winner.get("event_seq"),
                            "winner_entry_digest": winner.get("entry_digest"),
                            "idempotent_reuse": True,
                        }
            if normalized_kind in _TOOL_RESULT_KINDS:
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
            return await self._append_event_locked(
                session_id=session_id,
                event=event,
                existing_events=existing_events,
            )

    def _build_event(
        self,
        *,
        session_id: str,
        kind: str,
        event_type: str,
        **extra: Any,
    ) -> dict[str, Any]:
        resolved_session_id = str(session_id or "").strip()
        timestamp = datetime.now(UTC).isoformat()
        return {
            "ledger_schema_version": "1.0",
            "kind": str(kind),
            "event_type": str(event_type),
            "session_id": resolved_session_id,
            "run_id": resolved_session_id,
            "timestamp": timestamp,
            "tool_name": "",
            **dict(extra),
        }

    def _resolve_tool_invocation_manifest(
        self,
        *,
        session_id: str,
        payload: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        return normalize_tool_invocation_manifest(
            manifest=payload.get("tool_invocation_manifest")
            if isinstance(payload.get("tool_invocation_manifest"), dict)
            else None,
            run_id=str(session_id),
            tool_name_fallback=str(event.get("tool_name") or event.get("tool") or ""),
        )

    def _validate_ordering_contract(
        self,
        *,
        session_id: str,
        kind: str,
        payload: dict[str, Any],
        event: dict[str, Any],
        existing_events: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        normalized_kind = str(kind or "").strip()
        open_tool_calls = self._open_tool_calls(existing_events)
        next_seq = 1
        if existing_events:
            next_seq = max(self._event_sequence(row) for row in existing_events) + 1

        if normalized_kind == "run_finalized" and open_tool_calls:
            first_open = sorted(open_tool_calls)[0]
            return self._contract_rejection(
                session_id=session_id,
                error_code="E_ORPHANED_TOOL_CALL",
                open_call_sequence_number=first_open,
            )

        if normalized_kind == "tool_call" and open_tool_calls:
            first_open = sorted(open_tool_calls)[0]
            return self._contract_rejection(
                session_id=session_id,
                error_code="E_LEDGER_CALL_RESULT_ORDER",
                open_call_sequence_number=first_open,
            )

        if normalized_kind in _TOOL_RESULT_KINDS:
            raw_call_seq = payload.get("call_sequence_number")
            try:
                call_seq = int(raw_call_seq)
            except (TypeError, ValueError):
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_CALL_SEQUENCE_REQUIRED",
                )
            if call_seq <= 0 or call_seq >= int(next_seq):
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_CALL_SEQUENCE_INVALID",
                    call_sequence_number=call_seq,
                )
            call_event = self._event_by_sequence(existing_events, call_seq)
            if call_event is None or str(call_event.get("kind") or "") != "tool_call":
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_CALL_SEQUENCE_UNKNOWN",
                    call_sequence_number=call_seq,
                )
            if call_seq not in open_tool_calls:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_CALL_SEQUENCE_ALREADY_CLOSED",
                    call_sequence_number=call_seq,
                )
            expected_tool_call_hash = str(call_event.get("tool_call_hash") or "").strip()
            observed_tool_call_hash = str(event.get("tool_call_hash") or payload.get("tool_call_hash") or "").strip()
            if not observed_tool_call_hash:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_TOOL_CALL_HASH_REQUIRED",
                )
            if expected_tool_call_hash and observed_tool_call_hash != expected_tool_call_hash:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_TOOL_CALL_HASH_MISMATCH",
                )
            event["call_sequence_number"] = int(call_seq)
            event["tool_call_hash"] = observed_tool_call_hash
            if not str(event.get("tool_name") or "").strip():
                event["tool_name"] = str(call_event.get("tool_name") or "")

        artifact_hash = str(event.get("artifact_hash") or payload.get("artifact_hash") or "").strip()
        if artifact_hash and normalized_kind not in _TOOL_RESULT_KINDS:
            raw_call_seq = payload.get("call_sequence_number")
            try:
                call_seq = int(raw_call_seq)
            except (TypeError, ValueError):
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_ARTIFACT_CALL_SEQUENCE_REQUIRED",
                )
            if call_seq <= 0:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_ARTIFACT_CALL_SEQUENCE_REQUIRED",
                )
            if call_seq in open_tool_calls:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_ARTIFACT_EMIT_BEFORE_RESULT",
                    call_sequence_number=call_seq,
                )
            result_event = self._result_event_by_call_sequence(existing_events, call_seq)
            if result_event is None:
                return self._contract_rejection(
                    session_id=session_id,
                    error_code="E_ARTIFACT_RESULT_MISSING",
                    call_sequence_number=call_seq,
                )
            event["artifact_hash"] = artifact_hash
            event["call_sequence_number"] = int(call_seq)
        return None

    def _contract_rejection(
        self,
        *,
        session_id: str,
        error_code: str,
        **extra: Any,
    ) -> dict[str, Any]:
        return {
            "kind": "ledger_contract_rejected",
            "session_id": str(session_id),
            "run_id": str(session_id),
            "error_code": str(error_code),
            **dict(extra),
        }

    @staticmethod
    def _event_sequence(event: dict[str, Any]) -> int:
        return int(event.get("event_seq") or event.get("sequence_number") or 0)

    def _open_tool_calls(self, events: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
        open_calls: dict[int, dict[str, Any]] = {}
        for row in events:
            kind = str(row.get("kind") or "")
            event_seq = self._event_sequence(row)
            if event_seq <= 0:
                continue
            if kind == "tool_call":
                open_calls[event_seq] = dict(row)
                continue
            if kind in _TOOL_RESULT_KINDS:
                call_seq = int(row.get("call_sequence_number") or 0)
                if call_seq > 0:
                    open_calls.pop(call_seq, None)
        return open_calls

    def _event_by_sequence(self, events: list[dict[str, Any]], sequence_number: int) -> dict[str, Any] | None:
        target = int(sequence_number)
        for row in events:
            if self._event_sequence(row) == target:
                return dict(row)
        return None

    def _result_event_by_call_sequence(
        self,
        events: list[dict[str, Any]],
        call_sequence_number: int,
    ) -> dict[str, Any] | None:
        target = int(call_sequence_number)
        for row in events:
            kind = str(row.get("kind") or "")
            if kind not in _TOOL_RESULT_KINDS:
                continue
            if int(row.get("call_sequence_number") or 0) == target:
                return dict(row)
        return None

    async def _append_event_locked(
        self,
        *,
        session_id: str,
        event: dict[str, Any],
        existing_events: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        existing = existing_events
        if existing is None:
            existing = await asyncio.to_thread(self._ledger(session_id).replay_events)
        if existing:
            previous_ts = str(existing[-1].get("timestamp") or "").strip()
            current_ts = str(event.get("timestamp") or "").strip()
            if previous_ts and current_ts and current_ts < previous_ts:
                raise ValueError("E_LEDGER_TIMESTAMP_NON_MONOTONIC")
        next_seq = await asyncio.to_thread(self._ledger(session_id).next_event_seq)
        payload = dict(event)
        if int(payload.get("sequence_number") or 0) <= 0:
            payload["sequence_number"] = int(next_seq)
        appended = await asyncio.to_thread(self._ledger(session_id).append_event, payload)
        appended["sequence_number"] = int(appended.get("event_seq") or appended.get("sequence_number") or next_seq)
        return appended

    def _tool_invocation_count(self, events: list[dict[str, Any]]) -> int:
        return sum(
            1
            for row in events
            if str(row.get("kind") or "") in _TOOL_INVOCATION_KINDS
        )

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

    async def _duplicate_operation_rejection_locked(
        self,
        *,
        session_id: str,
        operation_id: str,
        kind: str,
        payload: Dict[str, Any],
    ) -> dict[str, Any] | None:
        registry = self._operation_registry(session_id)
        winner = await asyncio.to_thread(registry.winner, operation_id)
        if winner is None:
            return None
        entry_digest = hash_canonical_json(
            {
                "kind": str(kind),
                "payload": dict(payload or {}),
            }
        )
        winner_entry_digest = str(winner.get("entry_digest") or "")
        return {
            "kind": "operation_rejected",
            "session_id": str(session_id),
            "operation_id": str(operation_id),
            "error_code": "E_DUPLICATE_OPERATION",
            "winner_event_seq": winner.get("event_seq"),
            "winner_entry_digest": winner.get("entry_digest"),
            "idempotent_reuse": bool(entry_digest == winner_entry_digest),
        }

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
                raise ValueError(f"{E_RECEIPT_SEQ_INVALID_PREFIX}:{raw_seq}") from exc
            if int(normalized["receipt_seq"]) <= last_seq:
                raise ValueError(
                    f"{E_RECEIPT_SEQ_NON_MONOTONIC_PREFIX}:{normalized['receipt_seq']}<=last:{last_seq}"
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
                    raise ValueError(f"{E_RECEIPT_LOG_PARSE_PREFIX}:line={line_index}") from exc
                if not isinstance(parsed, dict):
                    raise ValueError(f"{E_RECEIPT_LOG_SCHEMA_PREFIX}:line={line_index}")
                rows.append(dict(parsed))
        rows.sort(
            key=lambda row: (
                int(row.get("receipt_seq") or 0),
                str(row.get("receipt_digest") or ""),
            )
        )
        return rows
