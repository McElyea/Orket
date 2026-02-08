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
    UTILITY = "utility"
    APP = "app"

class CardStatus(str, enum.Enum):
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    CANCELED = "canceled"
    WAITING_FOR_DEVELOPER = "waiting_for_developer"
    READY_FOR_TESTING = "ready_for_testing"
    CODE_REVIEW = "code_review"
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

class QualityAssessment(BaseModel):
    score: float
    grade: str # e.g. "Shippable", "Non-Shippable"
    audit_date: str
    criteria_scores: Dict[str, float]
    summary: str
    shippability_threshold: float = 7.0

class ArchitectureGovernance(BaseModel):
    idesign: bool = Field(default=True)
    pattern: str = Field(default="Standard")
    reasoning: Optional[str] = None

class LessonsLearned(BaseModel):
    date: str
    category: str
    observation: str
    sentiment: str = Field(default="negative") # "positive" or "negative"
    action_item: Optional[str] = None

class EpicConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.EPIC)
    team: str
    environment: str
    iterations: int = Field(1)
    handshake_enabled: bool = Field(default=False)
    issues: List[IssueConfig] = Field(default_factory=list, alias="stories")
    example_task: Optional[str] = None
    requirements: Optional[str] = None # High-level spec or link
    architecture_governance: ArchitectureGovernance = Field(default_factory=ArchitectureGovernance)
    quality_assessment: Optional[QualityAssessment] = None
    lessons_learned: List[LessonsLearned] = Field(default_factory=list)

class RockConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ROCK)
    task: Optional[str] = None
    epics: List[Dict[str, str]] # List of {epic: name, department: dept}
    quality_assessment: Optional[QualityAssessment] = None
    lessons_learned: List[LessonsLearned] = Field(default_factory=list)

# Recursive type for the Preview/Full Tree view
class CardDetail(BaseCardConfig):
    children: List[CardDetail] = []

# ---------------------------------------------------------------------------
# 4. Teams & Organization
# ---------------------------------------------------------------------------
class RoleConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.UTILITY)
    description: str
    prompt: Optional[str] = None
    tools: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)

class SeatConfig(BaseModel):
    name: str
    roles: List[str]

class TeamConfig(BaseModel):
    name: str
    description: Optional[str] = None
    seats: Dict[str, SeatConfig]
    roles: Optional[Dict[str, RoleConfig]] = Field(default_factory=dict)

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

class BrandingConfig(BaseModel):

    colorscheme: Dict[str, str] = Field(default_factory=dict)

    fonts: List[str] = Field(default_factory=list)

    logo_path: Optional[str] = None

    design_dos: List[str] = Field(default_factory=list)

    design_donts: List[str] = Field(default_factory=list)



class ArchitecturePrescription(BaseModel):

    idesign_threshold: int = Field(default=10, description="Number of issues in an Epic before iDesign is mandatory.")

    preferred_stack: Dict[str, str] = Field(default_factory=dict)

    cicd_rules: List[str] = Field(default_factory=list)



class ContactInfo(BaseModel):

    email: Optional[str] = None

    website: Optional[str] = None

    socials: Dict[str, str] = Field(default_factory=dict)



class OrganizationConfig(BaseModel):

    name: str

    vision: str

    ethos: str

    branding: BrandingConfig = Field(default_factory=BrandingConfig)

    architecture: ArchitecturePrescription = Field(default_factory=ArchitecturePrescription)

    contact: ContactInfo = Field(default_factory=ContactInfo)

    departments: List[str] = Field(default_factory=list)

    process_rules: Dict[str, Any] = Field(default_factory=dict)
