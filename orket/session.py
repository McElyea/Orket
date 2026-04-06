# orket/session.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class Message:
    role: str
    content: str
    ts: str


@dataclass
class Session:
    id: str
    type: str  # 'rock', 'epic', 'issue'
    name: str
    department: str
    status: str = "started"
    task_input: str = ""
    transcript: list[dict[str, Any]] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None

    @classmethod
    def start(cls, session_id: str, card_type: str, name: str, department: str, task_input: str) -> "Session":
        return cls(id=session_id, type=card_type, name=name, department=department, task_input=task_input)

    def add_turn(self, turn_data: dict[str, Any]) -> None:
        self.transcript.append(turn_data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "task_input": self.task_input,
            "transcript": self.transcript,
            "start_time": self.start_time,
            "end_time": self.end_time,
        }
