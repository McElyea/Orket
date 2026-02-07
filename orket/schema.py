from __future__ import annotations
from typing import Dict, List, Optional, Any
import uuid
import enum
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# 1. Environment
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

# ---------------------------------------------------------------------------
# 2. Role & Seat
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

# ---------------------------------------------------------------------------
# 3. Book & Epic (The Traction Board)
# ---------------------------------------------------------------------------
class BookType(str, enum.Enum):
    STORY = "story"
    BUG = "bug"
    PROD_SUPPORT = "prod_support"

class BookStatus(str, enum.Enum):
    READY = "ready"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    READY_FOR_TESTING = "ready_for_testing"
    WAITING_FOR_DEVELOPER = "waiting_for_developer"
    DONE = "done"
    CANCELED = "canceled"
    EXCUSE_REQUESTED = "excuse_requested"

class BookConfig(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    type: BookType = Field(default=BookType.STORY)
    summary: str
    seat: str
    status: BookStatus = Field(default=BookStatus.READY)
    priority: str = Field(default="Medium")
    assignee: Optional[str] = None
    sprint: Optional[str] = None
    note: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)

class EpicConfig(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: str
    description: Optional[str] = None
    team: str
    environment: str
    iterations: int = Field(1)
    books: List[BookConfig] = Field(default_factory=list, alias="stories")
    references: List[str] = Field(default_factory=list)
    example_task: Optional[str] = None

# ---------------------------------------------------------------------------
# 4. Rock
# ---------------------------------------------------------------------------
class RockConfig(BaseModel):
    name: str
    description: Optional[str] = None
    owner_department: str
    task: Optional[str] = None
    epics: List[Dict[str, str]]
    references: List[str] = Field(default_factory=list)

# ---------------------------------------------------------------------------
# 5. Organization & Engines
# ---------------------------------------------------------------------------
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
    mappings: Dict[str, EngineMapping] # e.g. "coder" -> Mapping

class DepartmentConfig(BaseModel):
    name: str
    description: Optional[str] = None
    policy: Dict[str, Any] = Field(default_factory=dict)

class OrganizationConfig(BaseModel):
    name: str
    vision: str
    departments: List[str]
