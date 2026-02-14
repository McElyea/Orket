from __future__ import annotations
from typing import Dict, List, Optional, Any, Union
import uuid
import enum
from pydantic import BaseModel, Field, ConfigDict, AliasChoices, field_validator
from orket.core.types import CardStatus, WaitReason, CardType
from orket.core.bottlenecks import BottleneckThresholds

# ---------------------------------------------------------------------------
# 1. Environment & Dialect
# ---------------------------------------------------------------------------
class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    schema_version: str = "1.0.0"
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
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)

class DialectConfig(BaseModel):
    model_family: str
    dsl_format: str
    constraints: List[str]
    hallucination_guard: str
    system_prefix: str = ""
    tool_call_syntax: Optional[str] = None
    style_guidelines: List[str] = Field(default_factory=list)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# 2. Card Fundamentals (Universal Base)
# ---------------------------------------------------------------------------
class BaseCardConfig(BaseModel):
    """
    The polymorphic base for all Orket Units of Work.
    Rocks, Epics, and Issues ARE Cards.
    """
    model_config = ConfigDict(populate_by_name=True, extra='ignore')
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: Optional[str] = Field(None, alias="summary")
    type: CardType = Field(default=CardType.ISSUE)
    status: CardStatus = Field(default=CardStatus.READY)
    description: Optional[str] = None
    priority: Union[float, str] = Field(default=2.0)  # 3.0=High, 2.0=Medium, 1.0=Low
    wait_reason: Optional[WaitReason] = None  # Why is this card blocked/waiting?
    note: Optional[str] = None

    # Hierarchy
    parent_id: Optional[str] = None
    build_id: Optional[str] = None

    # Metadata
    owner_department: Optional[str] = "core"
    labels: List[str] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    references: List[str] = Field(default_factory=list)

    @field_validator('priority', mode='before')
    @classmethod
    def convert_priority(cls, v):
        """Migrate legacy string priorities to numeric values."""
        if isinstance(v, str):
            # 1. Handle actual level keywords
            mapping = {"high": 3.0, "medium": 2.0, "low": 1.0}
            val = mapping.get(v.lower())
            if val is not None:
                return val
            
            # 2. Handle strings that are already numbers (e.g. '3.0')
            try:
                return float(v)
            except ValueError:
                raise ValueError(f"Unrecognized priority level: '{v}'. Expected 'High', 'Medium', 'Low', or a numeric value.")
        return v

# ---------------------------------------------------------------------------
# 3. Specific Card Implementations
# ---------------------------------------------------------------------------

class IssueMetrics(BaseModel):
    score: float = 0.0
    grade: str = "Pending"  # e.g. "Shippable", "Non-Shippable"
    audit_date: Optional[str] = None
    criteria_scores: Dict[str, float] = Field(default_factory=dict)
    shippability_threshold: float = 7.0
    path_delta: Optional[float] = 0.0  # Metric for Critical Path drift

class VerificationScenario(BaseModel) :
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:4])
    description: str
    input_data: Dict[str, Any]
    expected_output: Any
    actual_output: Optional[Any] = None
    status: str = Field(default="pending") # "pass", "fail", "pending"

class VerificationResult(BaseModel):
    timestamp: str
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    logs: List[str] = Field(default_factory=list)

class IssueVerification(BaseModel):
    fixture_path: Optional[str] = Field(None, validation_alias=AliasChoices("fixture_path", "verification_fixture"))
    scenarios: List[VerificationScenario] = Field(default_factory=list)
    last_run: Optional[VerificationResult] = Field(None, validation_alias=AliasChoices("last_run", "last_verification"))

class IssueConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ISSUE)
    seat: str = "standard"
    assignee: Optional[str] = None
    sprint: Optional[str] = None
    requirements: Optional[str] = None # Atomic requirement detail
    depends_on: List[str] = Field(default_factory=list)
    
    # Governance & Retries
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)

    # Separated Concerns
    verification: IssueVerification = Field(default_factory=IssueVerification)
    metrics: IssueMetrics = Field(default_factory=IssueMetrics)

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
    issues: List[IssueConfig] = Field(default_factory=list, validation_alias=AliasChoices("issues", "stories", "cards"))
    example_task: Optional[str] = None
    requirements: Optional[str] = None # High-level spec or link
    architecture_governance: ArchitectureGovernance = Field(default_factory=ArchitectureGovernance)
    metrics: Optional[IssueMetrics] = None
    lessons_learned: List[LessonsLearned] = Field(default_factory=list)

class RockConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ROCK)
    task: Optional[str] = None
    epics: List[Dict[str, str]] # List of {epic: name, department: dept}
    metrics: Optional[IssueMetrics] = None
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
    capabilities: Dict[str, Any] = Field(default_factory=dict)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)

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
    parent: Optional[str] = "core"
    policy: Dict[str, Any] = Field(default_factory=dict)
    preferred_stack: Dict[str, str] = Field(default_factory=dict)
    default_llm: Optional[str] = None

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
    model_config = ConfigDict(extra='ignore')
    schema_version: str = "1.0.0"
    name: str

    vision: str

    ethos: str

    branding: BrandingConfig = Field(default_factory=BrandingConfig)

    architecture: ArchitecturePrescription = Field(default_factory=ArchitecturePrescription)

    contact: ContactInfo = Field(default_factory=ContactInfo)

    departments: List[str] = Field(default_factory=list)

    process_rules: Dict[str, Any] = Field(default_factory=dict)

    bottleneck_thresholds: BottleneckThresholds = Field(default_factory=BottleneckThresholds)
