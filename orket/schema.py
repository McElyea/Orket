from __future__ import annotations
from typing import Dict, List, Optional, Any, Union
import uuid
import enum
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# 1. Environment & Dialect
# ---------------------------------------------------------------------------
class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str
    description: Optional[str] = None
    model: str
    temperature: float = 0.0
    seed: Optional[int] = None
    timeout: int = 300
    params: Dict[str, Any] = Field(default_factory=dict)

class SkillConfig(BaseModel):
    name: str
    intent: str
    responsibilities: List[str]
    idesign_constraints: Optional[List[str]] = Field(default_factory=list)
    tools: List[str] = Field(default_factory=list)

class DialectConfig(BaseModel):
    model_family: str
    dsl_format: str
    constraints: List[str]
    hallucination_guard: str

# ---------------------------------------------------------------------------
# 2. Card Fundamentals (Universal Base)
# ---------------------------------------------------------------------------
class CardType(str, enum.Enum):
    ROCK = "rock"
    EPIC = "epic"
    ISSUE = "issue"

class CardStatus(str, enum.Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    CANCELED = "canceled"
    WAITING_FOR_DEVELOPER = "waiting_for_developer"
    READY_FOR_TESTING = "ready_for_testing"
    DONE = "done"

class BaseCardConfig(BaseModel):
    """
    The polymorphic base for all Orket Units of Work.
    Rocks, Epics, and Issues ARE Cards.
    """
    model_config = ConfigDict(populate_by_name=True)
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: Optional[str] = Field(None, alias="summary")
    type: CardType
    status: CardStatus = Field(default=CardStatus.READY)
    description: Optional[str] = None
    priority: str = Field(default="Medium")
    note: Optional[str] = None
    
    # Hierarchy
    parent_id: Optional[str] = None
    build_id: Optional[str] = None
    
    # Metadata
    owner_department: Optional[str] = "core"
    labels: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    references: List[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# 3. Specific Card Implementations
# ---------------------------------------------------------------------------

class IssueConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ISSUE)
    seat: str
    assignee: Optional[str] = None
    sprint: Optional[str] = None
    requirements: Optional[str] = None # Atomic requirement detail

class EpicConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.EPIC)
    team: str
    environment: str
    iterations: int = Field(1)
    handshake_enabled: bool = Field(default=False)
    issues: List[IssueConfig] = Field(default_factory=list, alias="stories")
    example_task: Optional[str] = None
    requirements: Optional[str] = None # High-level spec or link

class RockConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ROCK)
    task: Optional[str] = None
    epics: List[Dict[str, str]] # List of {epic: name, department: dept}

# Recursive type for the Preview/Full Tree view
class CardDetail(BaseCardConfig):
    children: List[CardDetail] = []

# ---------------------------------------------------------------------------
# 4. Teams & Organization
# ---------------------------------------------------------------------------
class RoleConfig(BaseModel):
    name: str
    description: str
    tools: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)

class SeatConfig(BaseModel):
    name: str
    roles: List[str]

class TeamConfig(BaseModel):
    name: str
    description: Optional[str] = None
    seats: Dict[str, SeatConfig]
    roles: Dict[str, RoleConfig]

class EngineRecommendation(BaseModel):
    model: str
    tier: str
    description: str

class EngineMapping(BaseModel):
    tier: str
    keywords: List[str]
    fallback: str
    catalog: List[EngineRecommendation] = Field(default_factory=list)

class EngineRegistry(BaseModel):
    name: str
    updated_at: str
    mappings: Dict[str, EngineMapping]

class DepartmentConfig(BaseModel):
    name: str
    description: Optional[str] = None
    policy: Dict[str, Any] = Field(default_factory=dict)

class OrganizationConfig(BaseModel):
    name: str
    vision: str
    departments: List[str]