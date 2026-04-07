from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class ToolCallErrorClass(StrEnum):
    GATE_BLOCKED = "gate_blocked"
    UNKNOWN_TOOL = "unknown_tool"
    EXECUTION_FAILED = "execution_failed"
    PARSE_PARTIAL = "parse_partial"
    TIMEOUT = "timeout"
    INTERCEPTOR_CRASH = "interceptor_crash"


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]
    result: Any | None = None
    error: str | None = None
    error_class: ToolCallErrorClass | None = None

    def __post_init__(self) -> None:
        if self.error_class is not None and not isinstance(self.error_class, ToolCallErrorClass):
            self.error_class = ToolCallErrorClass(str(self.error_class))


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
    partial_parse_failure: bool = False
    error: str | None = None
    error_class: ToolCallErrorClass | None = None

    def __post_init__(self) -> None:
        if self.error_class is not None and not isinstance(self.error_class, ToolCallErrorClass):
            self.error_class = ToolCallErrorClass(str(self.error_class))


@dataclass
class ExecutionResult:
    session_id: str
    turns: list[ExecutionTurn] = field(default_factory=list)
    status: str = "in_progress"

    def add_turn(self, turn: ExecutionTurn) -> None:
        self.turns.append(turn)
