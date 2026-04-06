from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator

from orket.schema import CardStatus, CardType


class IssueRecord(BaseModel):
    """
    A lightweight, type-safe representation of an Issue in the database.
    Used to prevent domain shape leakage from repositories.
    """

    id: str
    session_id: str | None = None
    build_id: str | None = None
    seat: str
    summary: str = Field(..., validation_alias=AliasChoices("summary", "name"))
    type: CardType = CardType.ISSUE
    priority: float = 2.0
    sprint: str | None = None
    status: CardStatus = CardStatus.READY
    assignee: str | None = None
    note: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    verification: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None

    @field_validator("priority", mode="before")
    @classmethod
    def convert_priority(cls, v):
        if isinstance(v, str):
            mapping = {"high": 3.0, "medium": 2.0, "low": 1.0}
            val = mapping.get(v.lower())
            if val is not None:
                return val
            try:
                return float(v)
            except ValueError:
                return 2.0
        return v


class CardRecord(BaseModel):
    """Generic card record for non-issue card types."""

    id: str
    type: CardType
    status: CardStatus
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)
