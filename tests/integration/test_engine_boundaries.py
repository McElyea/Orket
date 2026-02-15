import pytest
import json
import asyncio
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.schema import CardStatus, CardType
from orket.exceptions import ExecutionFailed, GovernanceViolation

class BoundaryTestProvider(LocalModelProvider):
    def __init__(self, behavior="illegal_transition"):
        self.model = "dummy"
        self.timeout = 300
        self.behavior = behavior

    async def complete(self, messages):
        if self.behavior == "illegal_transition":
            # Attempt to jump from READY straight to DONE (illegal for ISSUE)
            return ModelResponse(
                content="""```json
{"tool": "update_issue_status", "args": {"status": "done"}}
```""",
                raw={"model": "dummy", "total_tokens": 50}
            )
        elif self.behavior == "path_traversal":
            # Attempt to write outside agent_output/
            return ModelResponse(
                content="""```json
{"tool": "write_file", "args": {"path": "../secret.txt", "content": "pwned"}}
```""",
                raw={"model": "dummy", "total_tokens": 50}
            )
        return ModelResponse(content="No action", raw={})

@pytest.fixture
def setup_env(tmp_path):
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "roles").mkdir(parents=True)
    (root / "model" / "core" / "dialects").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail", "vision": "V", "ethos": "E",
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
        "departments": ["core"]
    }))

    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "R", "summary": "lead_architect", "type": "utility", "description": "D", 
        "tools": ["update_issue_status", "write_file"], "capabilities": {"issue_types": ["issue", "story"]}
    }))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({"name": "standard", "seats": {"lead_architect": {"name": "L", "roles": ["lead_architect"]}}}))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}))

    (root / "model" / "core" / "epics" / "boundary_epic.json").write_text(json.dumps({
        "id": "EPIC-B", "name": "Boundary", "type": "epic", "team": "standard", "environment": "standard",
        "description": "D", "architecture_governance": {"idesign": False},
        "issues": [{"id": "ISSUE-B", "summary": "S", "seat": "lead_architect"}]
    }))
    
    return root, workspace

@pytest.mark.asyncio
async def test_illegal_state_transition_blocked(setup_env, monkeypatch):
    root, workspace = setup_env
    db_path = str(root / "test_boundary.db")
    
    provider = BoundaryTestProvider(behavior="illegal_transition")
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    
    # We expect the engine to raise an exception, and the card should end up BLOCKED
    with pytest.raises(ExecutionFailed):
        await engine.run_card("boundary_epic")
    
    issue = await engine.cards.get_by_id("ISSUE-B")
    assert issue.status == CardStatus.BLOCKED
    
    # Verify policy report exists
    report_path = workspace / "agent_output" / "policy_violation_ISSUE-B.json"
    assert report_path.exists()
    
    report = json.loads(report_path.read_text())
    assert report["violation_type"] == "state_transition"

@pytest.mark.asyncio
async def test_path_traversal_blocked(setup_env, monkeypatch):
    root, workspace = setup_env
    db_path = str(root / "test_traversal.db")
    
    provider = BoundaryTestProvider(behavior="path_traversal")
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    
    with pytest.raises(GovernanceViolation):
        await engine.run_card("boundary_epic")
    
    issue = await engine.cards.get_by_id("ISSUE-B")
    assert issue.status == CardStatus.BLOCKED
    
    report_path = workspace / "agent_output" / "policy_violation_ISSUE-B.json"
    assert report_path.exists()
    
    report = json.loads(report_path.read_text())
    assert report["violation_type"] == "governance"
    assert "security scope contract not met" in report["detail"].lower()

