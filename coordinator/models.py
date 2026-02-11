from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class Card(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    payload: dict
    state: str
    claimed_by: Optional[str] = None
    lease_expires_at: Optional[float] = None
    result: Optional[dict] = None
    attempts: int = 0
    hedged_execution: bool

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        valid: set[Literal["OPEN", "CLAIMED", "DONE", "FAILED"]] = {
            "OPEN",
            "CLAIMED",
            "DONE",
            "FAILED",
        }
        if value not in valid:
            raise ValueError("state must be one of OPEN, CLAIMED, DONE, FAILED")
        return value

