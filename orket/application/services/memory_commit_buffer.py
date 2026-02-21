from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MemoryBuffer:
    run_id: str
    start_snapshot_id: int
    writes: List[Dict[str, Any]] = field(default_factory=list)
    state: str = "buffer_open"
    commit_id: str = ""
    commit_payload_fingerprint: str = ""
    reason_code: str = ""
    lease_owner: str = ""
    lease_expires_at: float = 0.0


class InMemoryCommitStore:
    """
    Minimal deterministic memory commit coordinator used for contract-level tests.
    """

    def __init__(self) -> None:
        self._current_snapshot_id = 0
        self._snapshots: Dict[int, List[Dict[str, Any]]] = {0: []}
        self._buffers: Dict[str, MemoryBuffer] = {}
        self._commit_payload_by_id: Dict[str, str] = {}

    def current_snapshot_id(self) -> int:
        return self._current_snapshot_id

    def open_buffer(self, run_id: str) -> int:
        snapshot_id = self._current_snapshot_id
        self._buffers[run_id] = MemoryBuffer(run_id=run_id, start_snapshot_id=snapshot_id)
        return snapshot_id

    def append_write(self, run_id: str, record: Dict[str, Any]) -> None:
        buffer = self._buffers[run_id]
        if buffer.state != "buffer_open":
            raise ValueError("buffer_not_open")
        buffer.writes.append(dict(record))

    def read_snapshot(self, snapshot_id: int) -> List[Dict[str, Any]]:
        return [dict(row) for row in self._snapshots.get(snapshot_id, [])]

    def request_commit(self, run_id: str, commit_id: str, commit_payload_fingerprint: str) -> None:
        buffer = self._buffers[run_id]
        if buffer.state != "buffer_open":
            raise ValueError("invalid_state_transition")
        buffer.state = "commit_pending"
        buffer.commit_id = str(commit_id)
        buffer.commit_payload_fingerprint = str(commit_payload_fingerprint)

    def _apply_commit(self, run_id: str) -> Optional[int]:
        buffer = self._buffers[run_id]
        commit_id = buffer.commit_id
        payload = buffer.commit_payload_fingerprint
        if not commit_id:
            raise ValueError("missing_commit_id")

        prior = self._commit_payload_by_id.get(commit_id)
        if prior is not None:
            if prior != payload:
                buffer.state = "commit_aborted"
                buffer.reason_code = "payload_mismatch"
                raise ValueError("payload_mismatch")
            buffer.state = "commit_applied"
            return None

        self._commit_payload_by_id[commit_id] = payload
        next_snapshot = self._current_snapshot_id + 1
        merged = self.read_snapshot(buffer.start_snapshot_id) + [dict(row) for row in buffer.writes]
        self._snapshots[next_snapshot] = merged
        self._current_snapshot_id = next_snapshot
        buffer.state = "commit_applied"
        return next_snapshot

    def apply_commit(self, run_id: str) -> Optional[int]:
        buffer = self._buffers[run_id]
        if buffer.state != "commit_pending":
            raise ValueError("commit_not_pending")
        return self._apply_commit(run_id)

    def try_acquire_recovery_lease(self, run_id: str, worker_id: str, now_ts: float, lease_seconds: float) -> bool:
        buffer = self._buffers[run_id]
        if buffer.state != "commit_pending":
            return False
        owner = buffer.lease_owner.strip()
        if owner and owner != worker_id and buffer.lease_expires_at > now_ts:
            return False
        buffer.lease_owner = worker_id
        buffer.lease_expires_at = float(now_ts + lease_seconds)
        return True

    def renew_recovery_lease(self, run_id: str, worker_id: str, now_ts: float, lease_seconds: float) -> bool:
        buffer = self._buffers[run_id]
        if buffer.state != "commit_pending":
            return False
        if buffer.lease_owner != worker_id:
            return False
        if buffer.lease_expires_at <= now_ts:
            return False
        buffer.lease_expires_at = float(now_ts + lease_seconds)
        return True

    def recover_pending_commit(
        self,
        run_id: str,
        *,
        worker_id: str,
        now_ts: float,
        lease_seconds: float,
        fail_apply: bool = False,
    ) -> Optional[int]:
        buffer = self._buffers[run_id]
        if buffer.state != "commit_pending":
            raise ValueError("commit_not_pending")
        if not self.try_acquire_recovery_lease(run_id, worker_id, now_ts, lease_seconds):
            raise ValueError("lease_not_acquired")
        if fail_apply:
            buffer.state = "commit_aborted"
            buffer.reason_code = "storage_apply_failed"
            return None
        return self._apply_commit(run_id)

    def buffer_state(self, run_id: str) -> str:
        return self._buffers[run_id].state

    def buffer_reason_code(self, run_id: str) -> str:
        return self._buffers[run_id].reason_code


class JsonFileCommitStore(InMemoryCommitStore):
    """
    File-backed commit coordinator used by persistence integration tests.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        super().__init__()
        self._load()

    def _serialize(self) -> Dict[str, Any]:
        return {
            "current_snapshot_id": self._current_snapshot_id,
            "snapshots": self._snapshots,
            "commit_payload_by_id": self._commit_payload_by_id,
            "buffers": {
                run_id: {
                    "run_id": buffer.run_id,
                    "start_snapshot_id": buffer.start_snapshot_id,
                    "writes": buffer.writes,
                    "state": buffer.state,
                    "commit_id": buffer.commit_id,
                    "commit_payload_fingerprint": buffer.commit_payload_fingerprint,
                    "reason_code": buffer.reason_code,
                    "lease_owner": buffer.lease_owner,
                    "lease_expires_at": buffer.lease_expires_at,
                }
                for run_id, buffer in self._buffers.items()
            },
        }

    def _load(self) -> None:
        if not self._path.exists():
            return
        payload = json.loads(self._path.read_text(encoding="utf-8"))
        self._current_snapshot_id = int(payload.get("current_snapshot_id", 0))
        snapshots = payload.get("snapshots", {})
        self._snapshots = {
            int(key): [dict(row) for row in (value or [])]
            for key, value in snapshots.items()
            if isinstance(value, list)
        }
        if self._current_snapshot_id not in self._snapshots:
            self._snapshots[self._current_snapshot_id] = []
        commits = payload.get("commit_payload_by_id", {})
        self._commit_payload_by_id = {str(k): str(v) for k, v in commits.items()}
        self._buffers = {}
        for run_id, row in (payload.get("buffers", {}) or {}).items():
            if not isinstance(row, dict):
                continue
            self._buffers[str(run_id)] = MemoryBuffer(
                run_id=str(row.get("run_id") or run_id),
                start_snapshot_id=int(row.get("start_snapshot_id", 0)),
                writes=[dict(item) for item in (row.get("writes") or []) if isinstance(item, dict)],
                state=str(row.get("state") or "buffer_open"),
                commit_id=str(row.get("commit_id") or ""),
                commit_payload_fingerprint=str(row.get("commit_payload_fingerprint") or ""),
                reason_code=str(row.get("reason_code") or ""),
                lease_owner=str(row.get("lease_owner") or ""),
                lease_expires_at=float(row.get("lease_expires_at", 0.0) or 0.0),
            )

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._serialize(), indent=2) + "\n", encoding="utf-8")

    def open_buffer(self, run_id: str) -> int:
        snapshot_id = super().open_buffer(run_id)
        self._persist()
        return snapshot_id

    def append_write(self, run_id: str, record: Dict[str, Any]) -> None:
        super().append_write(run_id, record)
        self._persist()

    def request_commit(self, run_id: str, commit_id: str, commit_payload_fingerprint: str) -> None:
        super().request_commit(run_id, commit_id, commit_payload_fingerprint)
        self._persist()

    def apply_commit(self, run_id: str) -> Optional[int]:
        result = super().apply_commit(run_id)
        self._persist()
        return result

    def try_acquire_recovery_lease(self, run_id: str, worker_id: str, now_ts: float, lease_seconds: float) -> bool:
        ok = super().try_acquire_recovery_lease(run_id, worker_id, now_ts, lease_seconds)
        self._persist()
        return ok

    def renew_recovery_lease(self, run_id: str, worker_id: str, now_ts: float, lease_seconds: float) -> bool:
        ok = super().renew_recovery_lease(run_id, worker_id, now_ts, lease_seconds)
        self._persist()
        return ok

    def recover_pending_commit(
        self,
        run_id: str,
        *,
        worker_id: str,
        now_ts: float,
        lease_seconds: float,
        fail_apply: bool = False,
    ) -> Optional[int]:
        result = super().recover_pending_commit(
            run_id,
            worker_id=worker_id,
            now_ts=now_ts,
            lease_seconds=lease_seconds,
            fail_apply=fail_apply,
        )
        self._persist()
        return result
