from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class Event:
    timestamp: str
    event: str
    data: Dict[str, Any]


class EventStream:
    """
    A session-wide event stream.
    The UI will subscribe to this.
    """

    def __init__(self):
        self.events: List[Event] = []

    def push(self, event: Event) -> None:
        self.events.append(event)

    def all(self) -> List[Event]:
        return self.events

    def last(self) -> Event:
        return self.events[-1] if self.events else None
