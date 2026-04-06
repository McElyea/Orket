from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]
    result: Any | None = None
    error: str | None = None


@dataclass
class ExecutionTurn:
    role: str
    issue_id: str
    thought: str | None = None
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    note: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    session_id: str
    turns: list[ExecutionTurn] = field(default_factory=list)
    status: str = "in_progress"

    def add_turn(self, turn: ExecutionTurn):
        self.turns.append(turn)
