# orket/session.py
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


@dataclass
class Message:
    role: str
    content: str
    ts: str


class ToolCallRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool: str = ""
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any | None = None
    error: str | None = None
    error_class: str | None = None


class TranscriptTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0.0"
    role: str
    summary: str
    turn_index: int = Field(ge=0)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_turn(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        payload.setdefault("schema_version", "1.0.0")
        payload.setdefault("role", str(payload.get("actor") or payload.get("from_role") or "unknown"))
        payload.setdefault("summary", str(payload.get("summary") or payload.get("content") or ""))
        payload.setdefault("turn_index", int(payload.get("turn_index") or payload.get("index") or 0))
        payload.setdefault("tool_calls", list(payload.get("tool_calls") or []))
        return payload


@dataclass
class Session:
    id: str
    type: str  # 'rock', 'epic', 'issue'
    name: str
    department: str
    status: str = "started"
    task_input: str = ""
    transcript: list[TranscriptTurn] = field(default_factory=list)
    start_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    end_time: str | None = None

    def __post_init__(self) -> None:
        self.transcript = [TranscriptTurn.model_validate(turn) for turn in self.transcript]

    @classmethod
    def start(cls, session_id: str, card_type: str, name: str, department: str, task_input: str) -> "Session":
        return cls(id=session_id, type=card_type, name=name, department=department, task_input=task_input)

    def add_turn(self, turn_data: TranscriptTurn | dict[str, Any]) -> None:
        self.transcript.append(TranscriptTurn.model_validate(turn_data))

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "name": self.name,
            "department": self.department,
            "status": self.status,
            "task_input": self.task_input,
            "transcript": [turn.model_dump(mode="json") for turn in self.transcript],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


__all__ = ["Message", "Session", "ToolCallRecord", "TranscriptTurn"]
