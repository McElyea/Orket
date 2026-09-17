"""Verified first-commit storage; synchronous operations belong to owned workers."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from orket.adapters.storage.local_file_lock import NativeFileLocks
from orket.adapters.storage.verified_file import write_verified_bytes
from orket.core.contracts.local_file_lock import LocalFileLockError
from orket.core.contracts.protocol_error_codes import E_OPERATION_REGISTRY_PREFIX, format_protocol_error
from orket.core.contracts.protocol_hashing import canonical_json


class OperationCommitRegistry:
    """Retain the first operation commit; contention and corrupt history fail closed."""

    side_effecting = True

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self._thread_lock = threading.RLock()

    @contextmanager
    def _hold(self):
        with self._thread_lock:
            if self.path is None:
                yield
            else:
                locks = NativeFileLocks(self.path, suffix=".owners", error_prefix=E_OPERATION_REGISTRY_PREFIX,
                                        empty_key_error="registry_key_required")
                try:
                    with locks.hold_sync("registry"):
                        yield
                except LocalFileLockError as exc:
                    raise LocalFileLockError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, str(exc))) from exc

    def commit(self, *, operation_id: str, event_seq: int, entry_digest: str) -> dict[str, Any]:
        op_id, digest = str(operation_id or "").strip(), str(entry_digest or "").strip()
        if not op_id or not digest:
            raise ValueError("operation_id and entry_digest are required")
        if not isinstance(event_seq, int) or isinstance(event_seq, bool) or event_seq <= 0:
            raise ValueError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "event_seq_invalid"))
        seq = event_seq
        with self._hold():
            entries = self._load()
            existing = entries.get(op_id)
            if existing is not None:
                return {
                    "accepted": False, "operation_id": op_id,
                    "winner_event_seq": existing["event_seq"], "winner_entry_digest": existing["entry_digest"],
                    "error_code": "E_DUPLICATE_OPERATION", "idempotent_reuse": digest == existing["entry_digest"],
                }
            entries[op_id] = {"operation_id": op_id, "event_seq": seq, "entry_digest": digest}
            self._persist(entries)
            self._entries = entries
            return {
                "accepted": True, "operation_id": op_id, "winner_event_seq": seq,
                "winner_entry_digest": digest, "error_code": None, "idempotent_reuse": False,
            }

    def winner(self, operation_id: str) -> dict[str, Any] | None:
        with self._hold():
            row = self._load().get(str(operation_id or "").strip())
            return None if row is None else dict(row)

    def entries(self) -> list[dict[str, Any]]:
        with self._hold():
            return self._ordered(self._load())

    @staticmethod
    def _ordered(entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(row) for _, row in sorted(entries.items(), key=lambda item: (item[1]["event_seq"], item[0]))]

    def _load(self) -> dict[str, dict[str, Any]]:
        if self.path is None:
            return {key: dict(row) for key, row in self._entries.items()}
        try:
            raw = self.path.read_bytes()
        except FileNotFoundError:
            return {}
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise ValueError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "corrupt")) from exc
        rows = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            raise ValueError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "corrupt"))
        loaded: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "corrupt"))
            op_id, digest = str(row.get("operation_id") or "").strip(), str(row.get("entry_digest") or "").strip()
            seq = row.get("event_seq")
            if (not op_id or not digest or not isinstance(seq, int) or isinstance(seq, bool)
                    or seq <= 0 or op_id in loaded):
                raise ValueError(format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "corrupt"))
            loaded[op_id] = {"operation_id": op_id, "event_seq": seq, "entry_digest": digest}
        return loaded

    def _persist(self, entries: dict[str, dict[str, Any]]) -> None:
        if self.path is None:
            return
        rendered = (canonical_json({"entries": self._ordered(entries)}) + "\n").encode("utf-8")
        write_verified_bytes(self.path, rendered,
                             error_code=format_protocol_error(E_OPERATION_REGISTRY_PREFIX, "write_unverified"))
