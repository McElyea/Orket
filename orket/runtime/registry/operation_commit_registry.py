from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from orket.runtime.registry.protocol_hashing import canonical_json


class OperationCommitRegistry:
    """
    First-commit-wins registry for `operation_id` race resolution.

    For each operation id, the first committed record becomes authoritative.
    Later attempts return deterministic duplicate metadata.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._entries: dict[str, dict[str, Any]] = {}
        self._loaded = False

    def commit(self, *, operation_id: str, event_seq: int, entry_digest: str) -> dict[str, Any]:
        self._ensure_loaded()
        op_id = str(operation_id or "").strip()
        if not op_id:
            raise ValueError("operation_id is required")
        seq = int(event_seq)
        digest = str(entry_digest or "").strip()
        if not digest:
            raise ValueError("entry_digest is required")

        existing = self._entries.get(op_id)
        if existing is None:
            row = {
                "operation_id": op_id,
                "event_seq": seq,
                "entry_digest": digest,
            }
            self._entries[op_id] = row
            self._persist()
            return {
                "accepted": True,
                "operation_id": op_id,
                "winner_event_seq": seq,
                "winner_entry_digest": digest,
                "error_code": None,
                "idempotent_reuse": False,
            }

        winner_event_seq = int(existing.get("event_seq") or 0)
        winner_digest = str(existing.get("entry_digest") or "")
        return {
            "accepted": False,
            "operation_id": op_id,
            "winner_event_seq": winner_event_seq,
            "winner_entry_digest": winner_digest,
            "error_code": "E_DUPLICATE_OPERATION",
            "idempotent_reuse": bool(digest == winner_digest),
        }

    def winner(self, operation_id: str) -> dict[str, Any] | None:
        self._ensure_loaded()
        row = self._entries.get(str(operation_id or "").strip())
        if row is None:
            return None
        return dict(row)

    def entries(self) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return [
            dict(row)
            for _, row in sorted(
                self._entries.items(),
                key=lambda item: (int((item[1] or {}).get("event_seq") or 0), item[0]),
            )
        ]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if self.path is None or not self.path.exists():
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            self._entries = {}
            return
        rows = payload.get("entries") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            self._entries = {}
            return
        loaded: dict[str, dict[str, Any]] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            op_id = str(row.get("operation_id") or "").strip()
            digest = str(row.get("entry_digest") or "").strip()
            if not op_id or not digest:
                continue
            try:
                seq = int(row.get("event_seq") or 0)
            except (TypeError, ValueError):
                continue
            if seq <= 0:
                continue
            loaded[op_id] = {"operation_id": op_id, "event_seq": seq, "entry_digest": digest}
        self._entries = loaded

    def _persist(self) -> None:
        if self.path is None:
            return
        payload = {"entries": self.entries()}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(canonical_json(payload) + "\n", encoding="utf-8")
