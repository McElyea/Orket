from datetime import datetime
from typing import List, Optional, Dict
from pydantic import BaseModel, Field

class Note(BaseModel):
    """
    An ephemeral piece of inter-agent communication.
    Notes allow agents to pass tactical directives or findings 
    without polluting the global task description.
    """
    id: str = Field(default_factory=lambda: str(datetime.now().timestamp()))
    from_role: str
    to_role: Optional[str] = None  # None = Broadcast to all
    content: str
    created_at: datetime = Field(default_factory=datetime.now)
    step_index: int

class NoteStore:
    """
    A per-session memory bank for inter-agent notes.
    Only the orchestrator should mutate this store.
    """
    def __init__(self):
        self._notes: List[Note] = []

    def add(self, note: Note):
        self._notes.append(note)

    def get_for_role(self, role: str, up_to_step: int) -> List[Note]:
        """Returns all notes visible to a specific role at a specific turn."""
        visible = []
        for n in self._notes:
            if n.step_index >= up_to_step:
                continue
            if n.to_role is None or n.to_role == role:
                visible.append(n)
        return visible

    def all(self) -> List[Note]:
        return self._notes

    def clear(self):
        self._notes = []
