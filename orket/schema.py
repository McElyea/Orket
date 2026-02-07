from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# 1. Environment (formerly Venue)
# ---------------------------------------------------------------------------
class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    name: str
    description: Optional[str] = None
    model: str
    temperature: float = 0.0
    seed: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=dict)

# ---------------------------------------------------------------------------
# 2. Team (formerly Band)
# ---------------------------------------------------------------------------
class RoleConfig(BaseModel):
    description: str
    tools: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)

class TeamConfig(BaseModel):
    name: str
    description: Optional[str] = None
    roles: Dict[str, RoleConfig]

# ---------------------------------------------------------------------------
# 3. Sequence (formerly Score)
# ---------------------------------------------------------------------------
class StepConfig(BaseModel):
    role: str
    note: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)

class SequenceConfig(BaseModel):
    name: str
    description: Optional[str] = None
    steps: List[StepConfig]

# ---------------------------------------------------------------------------
# 4. Project (formerly Flow)
# ---------------------------------------------------------------------------
class ProjectConfig(BaseModel):
    name: str
    description: Optional[str] = None
    team: str  # Name of the team file (e.g., "standard")
    environment: str # Name of the environment file
    sequence: str # Name of the sequence file
    example_task: Optional[str] = None # Example task description or reference

# ---------------------------------------------------------------------------
# 5. Department (The Namespace)
# ---------------------------------------------------------------------------
class DepartmentConfig(BaseModel):
    name: str
    description: Optional[str] = None
    policy: Dict[str, Any] = Field(default_factory=dict)
