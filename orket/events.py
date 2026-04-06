from dataclasses import dataclass
from typing import Any


@dataclass
class Event:
    timestamp: str
    event: str
    data: dict[str, Any]


class EventStream:
    """
    A session-wide event stream.
    The UI will subscribe to this.
    """

    def __init__(self):
        self.events: list[Event] = []

    def push(self, event: Event) -> None:
        self.events.append(event)

    def all(self) -> list[Event]:
        return self.events

    def last(self) -> Event | None:
        return self.events[-1] if self.events else None
