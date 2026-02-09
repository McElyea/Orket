"""
Sandbox Domain Model - Phase 3: Elegant Failure & Recovery

Represents an isolated deployment environment for Orket-generated projects.
Each sandbox runs a complete application stack (backend + frontend + database)
in Docker containers with allocated ports.
"""
from __future__ import annotations
from typing import Dict, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import enum


class SandboxStatus(str, enum.Enum):
    """Sandbox lifecycle states."""
    CREATING = "creating"      # Docker Compose up in progress
    RUNNING = "running"        # All containers healthy
    UNHEALTHY = "unhealthy"    # Some containers failed health check
    STOPPING = "stopping"      # Shutdown in progress
    STOPPED = "stopped"        # Containers stopped
    DELETED = "deleted"        # Resources cleaned up


class TechStack(str, enum.Enum):
    """Supported technology stacks for generated projects."""
    FASTAPI_REACT_POSTGRES = "fastapi-react-postgres"
    FASTAPI_VUE_MONGO = "fastapi-vue-mongo"
    CSHARP_RAZOR_EF = "csharp-razor-ef"
    NODE_REACT_POSTGRES = "node-react-postgres"
    DJANGO_REACT_POSTGRES = "django-react-postgres"


class PortAllocation(BaseModel):
    """Port assignments for a sandbox."""
    api: int                    # Backend API port (8001+)
    frontend: int               # Frontend port (3001+)
    database: int               # Database port (5433+ or 27018+)
    admin_tool: Optional[int] = None  # pgAdmin, Mongo Express, etc.


class Sandbox(BaseModel):
    """
    Domain Entity: Represents an isolated deployment environment.

    Lifecycle:
    1. Created when code_review approved → CREATING
    2. Docker Compose up → RUNNING
    3. UAT phase (user tests)
    4. Rock → Done → Bug Fix Phase
    5. Bug phase ends → STOPPING → DELETED
    """
    id: str                     # Unique sandbox identifier (rock-001, epic-002, etc.)
    rock_id: str                # Parent Rock that triggered this sandbox
    project_name: str           # Human-readable project name
    tech_stack: TechStack       # Technology stack for this project
    status: SandboxStatus = Field(default=SandboxStatus.CREATING)

    # Infrastructure
    ports: PortAllocation       # Allocated port numbers
    compose_project: str        # Docker Compose project name (for cleanup)
    workspace_path: str         # Path to project code

    # Lifecycle metadata
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    deployed_at: Optional[str] = None
    deleted_at: Optional[str] = None

    # Health tracking
    health_checks_passed: int = 0
    health_checks_failed: int = 0
    last_health_check: Optional[str] = None

    # Access URLs
    api_url: str                # http://localhost:8001
    frontend_url: str           # http://localhost:3001
    database_url: str           # postgresql://localhost:5433 or mongodb://localhost:27018
    admin_url: Optional[str] = None  # http://localhost:8081 (pgAdmin)

    # Logs and errors
    container_ids: Dict[str, str] = Field(default_factory=dict)  # service -> container_id
    last_error: Optional[str] = None


class SandboxRegistry(BaseModel):
    """
    Infrastructure: In-memory registry of active sandboxes.
    Persisted to SQLite for durability across Orket restarts.
    """
    sandboxes: Dict[str, Sandbox] = Field(default_factory=dict)  # sandbox_id -> Sandbox
    port_allocator: PortAllocator = Field(default_factory=lambda: PortAllocator())

    def register(self, sandbox: Sandbox) -> None:
        """Add sandbox to registry."""
        self.sandboxes[sandbox.id] = sandbox

    def unregister(self, sandbox_id: str) -> Optional[Sandbox]:
        """Remove sandbox from registry and return it."""
        return self.sandboxes.pop(sandbox_id, None)

    def get(self, sandbox_id: str) -> Optional[Sandbox]:
        """Retrieve sandbox by ID."""
        return self.sandboxes.get(sandbox_id)

    def list_active(self) -> List[Sandbox]:
        """List all non-deleted sandboxes."""
        return [s for s in self.sandboxes.values() if s.status != SandboxStatus.DELETED]


class PortAllocator(BaseModel):
    """
    Service: Allocates unique ports for sandboxes to avoid conflicts.

    Port ranges:
    - API:      8001-8099
    - Frontend: 3001-3099
    - Database: 5433-5532 (Postgres), 27018-27117 (Mongo)
    - Admin:    8081-8180
    """
    allocated_ports: Dict[str, int] = Field(default_factory=dict)  # sandbox_id -> base_port
    next_available_base: int = 1  # Increments for each sandbox

    def allocate(self, sandbox_id: str, tech_stack: TechStack) -> PortAllocation:
        """Allocate ports for a new sandbox."""
        if sandbox_id in self.allocated_ports:
            raise ValueError(f"Ports already allocated for sandbox {sandbox_id}")

        base = self.next_available_base
        self.allocated_ports[sandbox_id] = base
        self.next_available_base += 1

        # Allocate based on tech stack
        if "mongo" in tech_stack.value:
            return PortAllocation(
                api=8000 + base,
                frontend=3000 + base,
                database=27017 + base,
                admin_tool=8080 + base  # Mongo Express
            )
        else:  # Postgres or SQL Server
            return PortAllocation(
                api=8000 + base,
                frontend=3000 + base,
                database=5432 + base,
                admin_tool=8080 + base  # pgAdmin
            )

    def release(self, sandbox_id: str) -> None:
        """Release ports when sandbox is deleted."""
        self.allocated_ports.pop(sandbox_id, None)
