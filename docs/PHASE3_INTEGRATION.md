# Phase 3 Integration Guide: Elegant Failure & Recovery

This document explains how to integrate the Sandbox Orchestrator and Bug Fix Phase Manager into Orket's ExecutionPipeline.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ ExecutionPipeline                                           │
│   ↓                                                         │
│ Issue → IN_PROGRESS → CODE_REVIEW                           │
│                          ↓                                   │
│                    integrity_guard approves                  │
│                          ↓                                   │
│                  [HOOK: Create Sandbox]                      │
│                          ↓                                   │
│                    Sandbox RUNNING                           │
│                          ↓                                   │
│                    UAT Phase (User Tests)                    │
│                          ↓                                   │
│ Rock → DONE  →  [HOOK: Start Bug Fix Phase]                 │
│                          ↓                                   │
│              Bug Fix Phase (1-4 weeks)                       │
│                ↓         ↓         ↓                         │
│           Monitor    Extend?   Bugs Found                    │
│                          ↓                                   │
│              [HOOK: End Phase + Delete Sandbox]              │
│                          ↓                                   │
│              Migrate bugs to Phase 2 Rock                    │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Sandbox Orchestrator (`orket/services/sandbox_orchestrator.py`)
**Purpose**: Manages Docker Compose lifecycle for sandboxes

**Methods**:
- `create_sandbox()` - Generate docker-compose.yml, allocate ports, deploy
- `delete_sandbox()` - Stop containers, remove volumes, release ports
- `health_check()` - Verify containers are running
- `get_logs()` - Retrieve container logs

### 2. Bug Fix Phase Manager (`orket/domain/bug_fix_phase.py`)
**Purpose**: Manages post-deployment bug discovery window

**Methods**:
- `start_phase()` - Begin monitoring when Rock → DONE
- `update_metrics()` - Track bug discovery rate
- `check_and_extend()` - Extend phase if bug rate is high
- `end_phase()` - Migrate bugs to Phase 2 Rock, trigger cleanup

### 3. Domain Models (`orket/domain/sandbox.py`)
- `Sandbox` - Represents a running sandbox environment
- `SandboxRegistry` - Tracks all active sandboxes
- `PortAllocator` - Prevents port conflicts
- `TechStack` - Supported technology stacks

## Integration Points

### Hook 1: Sandbox Creation (CODE_REVIEW → *)

**Trigger**: When `integrity_guard` approves code review (status changes from CODE_REVIEW to DONE/other)

**Location**: `ExecutionPipeline.run_card()` or `ExecutionPipeline._execute_issue()`

**Implementation**:

```python
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.sandbox import TechStack, SandboxRegistry

# In ExecutionPipeline.__init__
self.sandbox_orchestrator = SandboxOrchestrator(
    workspace_root=self.workspace,
    registry=SandboxRegistry()
)

# In ExecutionPipeline._execute_issue() or status update handler
async def _handle_code_review_approval(self, issue_id: str, epic: EpicConfig):
    """Called when integrity_guard approves code review."""

    # Detect tech stack from workspace files
    tech_stack = self._detect_tech_stack(epic.name)

    # Create sandbox
    sandbox = await self.sandbox_orchestrator.create_sandbox(
        rock_id=epic.parent_id or epic.id,  # Parent Rock ID
        project_name=epic.name,
        tech_stack=tech_stack,
        workspace_path=str(self.workspace / epic.name)
    )

    log_event("sandbox_created", {
        "sandbox_id": sandbox.id,
        "rock_id": sandbox.rock_id,
        "frontend_url": sandbox.frontend_url,
        "api_url": sandbox.api_url
    }, self.workspace)

    # TODO: Notify user that sandbox is ready
    print(f"✅ Sandbox deployed: {sandbox.frontend_url}")
```

### Hook 2: Bug Fix Phase Start (Rock → DONE)

**Trigger**: When a Rock is marked DONE

**Location**: `ExecutionPipeline.run_card()` after Rock completes

**Implementation**:

```python
from orket.domain.bug_fix_phase import BugFixPhaseManager

# In ExecutionPipeline.__init__
self.bug_fix_manager = BugFixPhaseManager(
    organization_config=self.org.dict() if self.org else {}
)

# After Rock completion
async def _handle_rock_completion(self, rock_id: str):
    """Called when Rock is marked DONE."""

    # Start bug fix phase
    phase = self.bug_fix_manager.start_phase(rock_id)

    log_event("bug_phase_started", {
        "rock_id": rock_id,
        "duration_days": phase.current_duration_days,
        "scheduled_end": phase.scheduled_end
    }, self.workspace)

    # TODO: Schedule daily bug monitoring
    # TODO: Notify user that UAT phase has begun
    print(f"🐛 Bug Fix Phase started for Rock {rock_id} ({phase.current_duration_days} days)")
```

### Hook 3: Bug Phase Monitoring (Daily)

**Trigger**: Scheduled task (cron, background thread, or user-initiated)

**Location**: New background service or manual trigger

**Implementation**:

```python
async def monitor_bug_phases(self):
    """Run daily to check bug discovery rates and extend phases if needed."""

    for rock_id, phase in self.bug_fix_manager.active_phases.items():
        # Query bug Issues from card repository
        bug_issues = self.cards.find_by_parent(rock_id, status=["ready", "in_progress", "blocked"])
        critical_bugs = [b for b in bug_issues if b.get("priority", 2.0) >= 3.0]

        # Update metrics
        self.bug_fix_manager.update_metrics(
            rock_id,
            bug_issue_ids=[b["id"] for b in bug_issues],
            critical_bug_ids=[b["id"] for b in critical_bugs]
        )

        # Check if extension needed
        extended = self.bug_fix_manager.check_and_extend(rock_id)
        if extended:
            log_event("bug_phase_extended", {
                "rock_id": rock_id,
                "new_duration": phase.current_duration_days,
                "reason": phase.extensions[-1]["reason"]
            }, self.workspace)

        # Check if phase expired
        if phase.is_expired():
            await self._end_bug_phase(rock_id)
```

### Hook 4: Bug Phase End + Sandbox Cleanup

**Trigger**: Bug Fix Phase reaches scheduled_end

**Location**: Called by monitoring task

**Implementation**:

```python
async def _end_bug_phase(self, rock_id: str):
    """End bug fix phase and clean up sandbox."""

    # End phase, migrate bugs
    phase2_rock_id = self.bug_fix_manager.end_phase(rock_id, create_phase2_rock=True)

    if phase2_rock_id:
        # TODO: Create Phase 2 Rock with remaining bugs
        log_event("phase2_rock_created", {
            "rock_id": phase2_rock_id,
            "parent_rock": rock_id
        }, self.workspace)

    # Delete sandbox
    sandbox_id = f"sandbox-{rock_id}"
    try:
        await self.sandbox_orchestrator.delete_sandbox(sandbox_id)
        log_event("sandbox_deleted", {"sandbox_id": sandbox_id}, self.workspace)
        print(f"🗑️  Sandbox {sandbox_id} cleaned up")
    except Exception as e:
        log_event("sandbox_delete_failed", {
            "sandbox_id": sandbox_id,
            "error": str(e)
        }, self.workspace)
```

## Tech Stack Detection

**Helper method** to detect project type from workspace:

```python
def _detect_tech_stack(self, project_name: str) -> TechStack:
    """Detect technology stack from project files."""
    project_path = self.workspace / project_name

    # Check for specific markers
    if (project_path / "requirements.txt").exists() or (project_path / "pyproject.toml").exists():
        if (project_path / "package.json").exists():
            # Python backend + JS frontend
            if "vue" in (project_path / "package.json").read_text().lower():
                if (project_path / "mongo").exists() or "mongodb" in (project_path / ".env").read_text():
                    return TechStack.FASTAPI_VUE_MONGO
                else:
                    return TechStack.FASTAPI_REACT_POSTGRES  # Default
            else:
                return TechStack.FASTAPI_REACT_POSTGRES

    elif (project_path / "*.csproj").exists() or (project_path / "*.sln").exists():
        return TechStack.CSHARP_RAZOR_EF

    elif (project_path / "package.json").exists():
        # Node.js backend
        return TechStack.NODE_REACT_POSTGRES

    else:
        # Default fallback
        return TechStack.FASTAPI_REACT_POSTGRES
```

## Organizational Configuration

Add to `config/organization.json`:

```json
{
  "bug_fix_initial_days": 7,
  "bug_fix_max_days": 28,
  "bug_discovery_high_rate": 5.0,
  "bug_critical_threshold": 3
}
```

## Tools for Agents

**Optional**: Create agent tools to inspect sandboxes:

```python
# In orket/tools.py or new file

async def inspect_sandbox(args: Dict[str, Any], context: Dict) -> str:
    """Tool for agents to view sandbox status."""
    sandbox_id = args.get("sandbox_id")
    orchestrator = context.get("sandbox_orchestrator")

    sandbox = orchestrator.registry.get(sandbox_id)
    if not sandbox:
        return f"Sandbox {sandbox_id} not found"

    return json.dumps({
        "id": sandbox.id,
        "status": sandbox.status.value,
        "frontend_url": sandbox.frontend_url,
        "api_url": sandbox.api_url,
        "health_checks_passed": sandbox.health_checks_passed,
        "health_checks_failed": sandbox.health_checks_failed
    }, indent=2)

async def get_sandbox_logs(args: Dict[str, Any], context: Dict) -> str:
    """Tool for agents to retrieve sandbox logs."""
    sandbox_id = args.get("sandbox_id")
    service = args.get("service", None)  # api, frontend, database
    orchestrator = context.get("sandbox_orchestrator")

    return orchestrator.get_logs(sandbox_id, service)
```

## Testing

Create integration test:

```python
# tests/test_sandbox_lifecycle.py

import pytest
from orket.services.sandbox_orchestrator import SandboxOrchestrator
from orket.domain.sandbox import TechStack, SandboxRegistry
from orket.domain.bug_fix_phase import BugFixPhaseManager

@pytest.mark.asyncio
async def test_sandbox_lifecycle(tmp_path):
    """Test full sandbox creation → deletion flow."""

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    orchestrator = SandboxOrchestrator(workspace, SandboxRegistry())

    # Create sandbox
    sandbox = await orchestrator.create_sandbox(
        rock_id="ROCK-01",
        project_name="test-app",
        tech_stack=TechStack.FASTAPI_REACT_POSTGRES,
        workspace_path=str(workspace / "test-app")
    )

    assert sandbox.status == SandboxStatus.RUNNING
    assert sandbox.ports.api == 8001
    assert sandbox.ports.frontend == 3001

    # Health check
    healthy = await orchestrator.health_check(sandbox.id)
    assert healthy

    # Delete sandbox
    await orchestrator.delete_sandbox(sandbox.id)
    assert sandbox.status == SandboxStatus.DELETED
```

## Next Steps

1. ✅ Sandbox Orchestrator implemented
2. ✅ Bug Fix Phase Manager implemented
3. ⏳ Integrate hooks into ExecutionPipeline
4. ⏳ Add Gitea integration (push repos)
5. ⏳ Create agent tools for sandbox inspection
6. ⏳ Add daily bug monitoring scheduler
7. ⏳ Test end-to-end with real project

## Gitea Integration (Future)

When ready, integrate Gitea Actions to trigger sandbox rebuilds on PR:

```yaml
# .gitea/workflows/deploy-sandbox.yml
name: Deploy to Sandbox
on:
  pull_request:
    types: [closed]
    branches: [main]

jobs:
  deploy:
    if: github.event.pull_request.merged == true
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Orket Sandbox Rebuild
        run: |
          curl -X POST http://orket-api:5000/sandboxes/rebuild \
            -H "Content-Type: application/json" \
            -d '{"rock_id": "${{ env.ROCK_ID }}"}'
```
