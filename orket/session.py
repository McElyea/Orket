# orket/session.py
import uuid
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import List, Dict, Any


@dataclass
class Message:
    role: str
    content: str
    ts: str


@dataclass
class Session:
    id: str
    type: str # 'rock', 'epic', 'issue'
    name: str
    department: str
    status: str = "started"
    task_input: str = ""
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: Optional[str] = None

    @classmethod
    def start(cls, session_id: str, card_type: str, name: str, department: str, task_input: str) -> "Session":
        return cls(
            id=session_id,
            type=card_type,
            name=name,
            department=department,
            task_input=task_input
        )

    def add_turn(self, turn_data: Dict[str, Any]) -> None:
        self.transcript.append(turn_data)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "task_input": self.task_input,
            "transcript": self.transcript,
            "start_time": self.start_time,
            "end_time": self.end_time
        }
