from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


CardState = Literal["OPEN", "CLAIMED", "DONE", "FAILED"]


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    payload: Any
    state: CardState
    claimed_by: str | None = None
    lease_expires_at: datetime | None = None
    result: Any | None = None
    attempts: int = 0

