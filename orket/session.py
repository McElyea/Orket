# orket/session.py
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any


@dataclass
class Message:
    role: str
    content: str
    ts: str


@dataclass
class Session:
    id: str
    venue_name: str
    task: str
    messages: List[Message] = field(default_factory=list)

    @classmethod
    def start(cls, venue_name: str, task: str) -> "Session":
        return cls(
            id=str(uuid.uuid4()),
            venue_name=venue_name,
            task=task,
            messages=[
                Message(
                    role="user",
                    content=task,
                    ts=datetime.utcnow().isoformat() + "Z",
                )
            ],
        )

    def add_message(self, role: str, content: str) -> None:
        self.messages.append(
            Message(
                role=role,
                content=content,
                ts=datetime.utcnow().isoformat() + "Z",
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "venue": self.venue_name,
            "task": self.task,
            "messages": [
                {"role": m.role, "content": m.content, "ts": m.ts}
                for m in self.messages
            ],
        }
