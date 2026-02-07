from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict

# ---------------------------------------------------------------------------
# 1. Environment (The "Infrastructure")
# ---------------------------------------------------------------------------
class EnvironmentConfig(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    name: str
    description: Optional[str] = None
    model: str
    temperature: float = 0.0
    seed: Optional[int] = None
    params: Dict[str, Any] = Field(default_factory=list) # Changed to list for consistency if needed, but dict is better for params

# ---------------------------------------------------------------------------
# 2. Role & Seat (The "Accountability")
# ---------------------------------------------------------------------------
class RoleConfig(BaseModel):
    """A specific skill or persona (e.g., 'Python Coding', 'System Architecture')."""
    name: str
    description: str
    tools: List[str] = Field(default_factory=list)
    policy: Dict[str, Any] = Field(default_factory=dict)

class SeatConfig(BaseModel):
    """A 'Seat' on the bus. Has a name and a list of roles/responsibilities."""
    name: str
    roles: List[str] = Field(..., description="List of Role names this seat is responsible for.")

class TeamConfig(BaseModel):
    """The collection of Seats that make up a functional unit."""
    name: str
    description: Optional[str] = None
    seats: Dict[str, SeatConfig] = Field(..., description="Seat Name -> Seat Configuration")
    roles: Dict[str, RoleConfig] = Field(..., description="Role Name -> Role Configuration")

# ---------------------------------------------------------------------------
# 3. Story & Epic (The "Traction")
# ---------------------------------------------------------------------------
class StoryConfig(BaseModel):
    """A single 'To-Do' or Step in a sequence."""
    seat: str = Field(..., description="The Seat responsible for this story.")
    model: Optional[str] = Field(None, description="Optional model override for this specific story.")
    governance: Optional[str] = Field("always", description="Rule: 'always', 'once' (round 1 only), 'final' (last round only).")
    note: Optional[str] = None
    params: Dict[str, Any] = Field(default_factory=dict)

class EpicConfig(BaseModel):
    """A 'Sequence' of stories that deliver a major feature or fix."""
    name: str
    description: Optional[str] = None
    team: str  # Reference to Team file
    environment: str # Reference to Environment file
    iterations: int = Field(1, description="Number of times to repeat the stories (Rounds).")
    stories: List[StoryConfig]
    references: List[str] = Field(default_factory=list, description="List of read-only input paths (folders/files).")
    example_task: Optional[str] = None

# ---------------------------------------------------------------------------
# 4. Rock (The "90-Day Goal")
# ---------------------------------------------------------------------------
class RockConfig(BaseModel):
    """A high-level objective that coordinates Epics across Departments."""
    name: str
    description: Optional[str] = None
    owner_department: str
    epics: List[Dict[str, str]] = Field(..., description="List of {'department': '...', 'epic': '...'} pairs")
    references: List[str] = Field(default_factory=list, description="Global references for this Rock.")

# ---------------------------------------------------------------------------
# 5. Department & Organization
# ---------------------------------------------------------------------------
class DepartmentConfig(BaseModel):
    name: str
    description: Optional[str] = None
    policy: Dict[str, Any] = Field(default_factory=dict)

class OrganizationConfig(BaseModel):
    name: str
    vision: str
    departments: List[str]