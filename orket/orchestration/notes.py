from datetime import datetime

from pydantic import BaseModel


class Note(BaseModel):
    """
    An ephemeral piece of inter-agent communication.
    Notes allow agents to pass tactical directives or findings
    without polluting the global task description.
    """

    id: str
    from_role: str
    to_role: str | None = None  # None = Broadcast to all
    content: str
    created_at: datetime
    step_index: int


class NoteStore:
    """
    A per-session memory bank for inter-agent notes.
    Only the orchestrator should mutate this store.
    """

    def __init__(self) -> None:
        self._notes: list[Note] = []

    def add(self, note: Note) -> None:
        self._notes.append(note)

    def get_for_role(self, role: str, up_to_step: int) -> list[Note]:
        """Returns all notes visible to a specific role at a specific turn."""
        visible: list[Note] = []
        for n in self._notes:
            if n.step_index >= up_to_step:
                continue
            if n.to_role is None or n.to_role == role:
                visible.append(n)
        return visible

    def all(self) -> list[Note]:
        return list(self._notes)

    def clear(self) -> None:
        self._notes = []
