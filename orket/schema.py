from __future__ import annotations

import uuid
import warnings
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from orket.core.bottlenecks import BottleneckThresholds
from orket.core.types import CardStatus, CardType, WaitReason


# ---------------------------------------------------------------------------
# 1. Environment & Dialect
# ---------------------------------------------------------------------------
class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "1.0.0"
    name: str
    description: str | None = None
    model: str
    temperature: float = 0.0
    seed: int | None = None
    timeout: int = 300
    params: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def warn_on_unknown_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        unknown = sorted(set(data) - set(cls.model_fields))
        if unknown:
            warnings.warn(
                "EnvironmentConfig ignored unknown key(s): " + ", ".join(unknown),
                UserWarning,
                stacklevel=2,
            )
        return data


class SkillConfig(BaseModel):
    name: str
    intent: str
    responsibilities: list[str]
    idesign_constraints: list[str] | None = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    prompt_metadata: dict[str, Any] = Field(default_factory=dict)


class DialectConfig(BaseModel):
    model_family: str
    dsl_format: str
    constraints: list[str]
    hallucination_guard: str
    system_prefix: str = ""
    tool_call_syntax: str | None = None
    style_guidelines: list[str] = Field(default_factory=list)
    prompt_metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 2. Card Fundamentals (Universal Base)
# ---------------------------------------------------------------------------
class BaseCardConfig(BaseModel):
    """
    The polymorphic base for all Orket Units of Work.
    Rocks, Epics, and Issues ARE Cards.
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    name: str | None = Field(None, alias="summary")
    type: CardType = Field(default=CardType.ISSUE)
    status: CardStatus = Field(default=CardStatus.READY)
    description: str | None = None
    priority: float = Field(default=2.0)  # 3.0=High, 2.0=Medium, 1.0=Low
    wait_reason: WaitReason | None = None  # Why is this card blocked/waiting?
    note: str | None = None

    # Hierarchy
    parent_id: str | None = None
    build_id: str | None = None

    # Metadata
    owner_department: str | None = "core"
    labels: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    references: list[str] = Field(default_factory=list)

    @field_validator("priority", mode="before")
    @classmethod
    def convert_priority(cls, v: object) -> object:
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
            except ValueError as exc:
                raise ValueError(
                    f"Unrecognized priority level: '{v}'. Expected 'High', 'Medium', 'Low', or a numeric value."
                ) from exc
        return v


# ---------------------------------------------------------------------------
# 3. Specific Card Implementations
# ---------------------------------------------------------------------------


class IssueMetrics(BaseModel):
    score: float = 0.0
    grade: str = "Pending"  # e.g. "Shippable", "Non-Shippable"
    audit_date: str | None = None
    criteria_scores: dict[str, float] = Field(default_factory=dict)
    shippability_threshold: float = 7.0
    path_delta: float | None = 0.0  # Metric for Critical Path drift


class VerificationScenario(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:4])
    description: str
    input_data: dict[str, Any]
    expected_output: Any
    actual_output: Any | None = None
    status: str = Field(default="pending")  # "pass", "fail", "pending"


class VerificationResult(BaseModel):
    timestamp: str
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0
    logs: list[str] = Field(default_factory=list)


class IssueVerification(BaseModel):
    fixture_path: str | None = Field(None, validation_alias=AliasChoices("fixture_path", "verification_fixture"))
    scenarios: list[VerificationScenario] = Field(default_factory=list)
    last_run: VerificationResult | None = Field(None, validation_alias=AliasChoices("last_run", "last_verification"))


class IssueConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ISSUE)
    seat: str = "standard"
    assignee: str | None = None
    sprint: str | None = None
    requirements: str | None = None  # Atomic requirement detail
    depends_on: list[str] = Field(default_factory=list)

    # Governance & Retries
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)

    # Separated Concerns
    verification: IssueVerification = Field(default_factory=lambda: IssueVerification.model_construct())
    metrics: IssueMetrics = Field(default_factory=IssueMetrics)


class ArchitectureGovernance(BaseModel):
    idesign: bool = Field(default=False)
    pattern: str = Field(default="Standard")
    reasoning: str | None = None


class LessonsLearned(BaseModel):
    date: str
    category: str
    observation: str
    sentiment: str = Field(default="negative")  # "positive" or "negative"
    action_item: str | None = None


class EpicConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.EPIC)
    team: str
    environment: str
    iterations: int = Field(1)
    handshake_enabled: bool = Field(default=False)
    issues: list[IssueConfig] = Field(default_factory=list, validation_alias=AliasChoices("issues", "stories", "cards"))
    example_task: str | None = None
    requirements: str | None = None  # High-level spec or link
    architecture_governance: ArchitectureGovernance = Field(default_factory=ArchitectureGovernance)
    metrics: IssueMetrics | None = None
    lessons_learned: list[LessonsLearned] = Field(default_factory=list)


class RockConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.ROCK)
    task: str | None = None
    epics: list[dict[str, str]]  # List of {epic: name, department: dept}
    metrics: IssueMetrics | None = None
    lessons_learned: list[LessonsLearned] = Field(default_factory=list)


# Recursive type for the Preview/Full Tree view
class CardDetail(BaseCardConfig):
    children: list[CardDetail] = []


# ---------------------------------------------------------------------------
# 4. Teams & Organization
# ---------------------------------------------------------------------------
class RoleConfig(BaseCardConfig):
    type: CardType = Field(default=CardType.UTILITY)
    description: str
    prompt: str | None = None
    tools: list[str] = Field(default_factory=list)
    policy: dict[str, Any] = Field(default_factory=dict)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    prompt_metadata: dict[str, Any] = Field(default_factory=dict)


class SeatConfig(BaseModel):
    name: str
    roles: list[str]


class TeamConfig(BaseModel):
    name: str
    description: str | None = None
    seats: dict[str, SeatConfig]
    roles: dict[str, RoleConfig] | None = Field(default_factory=dict)


class EngineRecommendation(BaseModel):
    model: str
    tier: str
    description: str


class EngineMapping(BaseModel):
    tier: str
    keywords: list[str]
    fallback: str
    catalog: list[EngineRecommendation] = Field(default_factory=list)


class EngineRegistry(BaseModel):
    name: str
    updated_at: str
    mappings: dict[str, EngineMapping]


class DepartmentConfig(BaseModel):
    name: str
    description: str | None = None
    parent: str | None = "core"
    policy: dict[str, Any] = Field(default_factory=dict)
    preferred_stack: dict[str, str] = Field(default_factory=dict)
    default_llm: str | None = None


class BrandingConfig(BaseModel):
    colorscheme: dict[str, str] = Field(default_factory=dict)

    fonts: list[str] = Field(default_factory=list)

    logo_path: str | None = None

    design_dos: list[str] = Field(default_factory=list)

    design_donts: list[str] = Field(default_factory=list)


class ArchitecturePrescription(BaseModel):
    idesign_threshold: int = Field(
        default=10, description="Legacy iDesign threshold (inactive unless iDesign mode is explicitly enabled)."
    )

    preferred_stack: dict[str, str] = Field(default_factory=dict)

    cicd_rules: list[str] = Field(default_factory=list)


class ContactInfo(BaseModel):
    email: str | None = None

    website: str | None = None

    socials: dict[str, str] = Field(default_factory=dict)


class OrganizationConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    schema_version: str = "1.0.0"
    name: str

    vision: str

    ethos: str

    branding: BrandingConfig = Field(default_factory=BrandingConfig)

    architecture: ArchitecturePrescription = Field(default_factory=ArchitecturePrescription)

    contact: ContactInfo = Field(default_factory=ContactInfo)

    departments: list[str] = Field(default_factory=list)

    process_rules: dict[str, Any] = Field(default_factory=dict)

    allowed_idesign_categories: list[str] | None = None

    bottleneck_thresholds: BottleneckThresholds = Field(default_factory=lambda: BottleneckThresholds.model_construct())


__all__ = [
    "ArchitectureGovernance",
    "ArchitecturePrescription",
    "BaseCardConfig",
    "BrandingConfig",
    "CardDetail",
    "CardStatus",
    "CardType",
    "ContactInfo",
    "DepartmentConfig",
    "DialectConfig",
    "EngineMapping",
    "EngineRecommendation",
    "EngineRegistry",
    "EnvironmentConfig",
    "EpicConfig",
    "IssueConfig",
    "IssueMetrics",
    "IssueVerification",
    "LessonsLearned",
    "OrganizationConfig",
    "RockConfig",
    "RoleConfig",
    "SeatConfig",
    "SkillConfig",
    "TeamConfig",
    "VerificationResult",
    "VerificationScenario",
    "WaitReason",
]
