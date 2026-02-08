from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime

@dataclass
class ToolCall:
    tool: str
    args: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None

@dataclass
class ExecutionTurn:
    role: str
    issue_id: str
    thought: Optional[str] = None
    content: str = ""
    tool_calls: List[ToolCall] = field(default_factory=list)
    tokens_used: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    note: str = ""

@dataclass
class ExecutionResult:
    session_id: str
    turns: List[ExecutionTurn] = field(default_factory=list)
    status: str = "in_progress"
    
    def add_turn(self, turn: ExecutionTurn):
        self.turns.append(turn)
