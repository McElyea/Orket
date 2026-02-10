from __future__ import annotations
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator, AliasChoices
from orket.schema import CardStatus, CardType

class IssueRecord(BaseModel):
    """
    A lightweight, type-safe representation of an Issue in the database.
    Used to prevent domain shape leakage from repositories.
    """
    id: str
    session_id: Optional[str] = None
    build_id: Optional[str] = None
    seat: str
    summary: str = Field(..., validation_alias=AliasChoices("summary", "name"))
    type: CardType = CardType.ISSUE
    priority: float = 2.0
    sprint: Optional[str] = None
    status: CardStatus = CardStatus.READY
    assignee: Optional[str] = None
    note: Optional[str] = None
    depends_on: List[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    verification: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None

    @field_validator('priority', mode='before')
    @classmethod
    def convert_priority(cls, v):
        """Migrate legacy string priorities to numeric values."""
        if isinstance(v, str):
            mapping = {"high": 3.0, "medium": 2.0, "low": 1.0}
            val = mapping.get(v.lower())
            if val is not None:
                return val
            try:
                return float(v)
            except ValueError:
                return 2.0 # Default
        return v

class CardRecord(BaseModel):
    """
    Generic card record for other card types.
    """
    id: str
    type: CardType
    status: CardStatus
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
