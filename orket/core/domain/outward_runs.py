from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class OutwardRunRecord:
    run_id: str
    status: str
    namespace: str
    submitted_at: str
    current_turn: int
    max_turns: int
    task: dict[str, Any]
    policy_overrides: dict[str, Any]
    pending_proposals: tuple[dict[str, Any], ...] = ()
    started_at: str | None = None
    completed_at: str | None = None
    stop_reason: str | None = None

    def to_status_payload(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status,
            "namespace": self.namespace,
            "submitted_at": self.submitted_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "stop_reason": self.stop_reason,
            "current_turn": self.current_turn,
            "max_turns": self.max_turns,
            "pending_proposals": list(self.pending_proposals),
        }


__all__ = ["OutwardRunRecord"]
