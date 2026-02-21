from __future__ import annotations

from dataclasses import dataclass, field
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
