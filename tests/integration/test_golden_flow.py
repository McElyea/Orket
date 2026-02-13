import pytest
import json
import asyncio
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.schema import CardStatus

class GoldenFlowDummyProvider(LocalModelProvider):
    def __init__(self):
        self.model = "dummy"
        self.timeout = 300
        self.turns = 0

    async def complete(self, messages):
        self.turns += 1
        # messages[0] is system prompt
        system_prompt = messages[0]["content"]
        
        if "CODE REVIEW" in system_prompt or "integrity_guard" in system_prompt.lower():
            # Verifier turn: finalize the card
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 50}
            )
        else:
            # Developer turn: create file in secure directory and move to review
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/sanity.txt", "content": "Orket is Operational"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 100}
            )

@pytest.mark.asyncio
async def test_golden_flow(tmp_path, monkeypatch):
    # 1. Setup temporary directory structure
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "roles").mkdir(parents=True)
    (root / "model" / "core" / "dialects").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir() # Required for secure write
    (workspace / "verification").mkdir() # Required for RCE fix
    
    db_path = str(root / "test_orket.db")

    # 2. Create mock assets
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail",
        "vision": "Test",
        "ethos": "Test",
        "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
        "departments": ["core"]
    }))

    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name,
            "dsl_format": "JSON",
            "constraints": [],
            "hallucination_guard": "None"
        }))

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "ARCH",
        "summary": "lead_architect",
        "type": "utility",
        "description": "Test Architect",
        "prompt": "Test Prompt",
        "tools": ["write_file", "update_issue_status"]
    }))
    
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "VERI",
        "summary": "integrity_guard",
        "type": "utility",
        "description": "Test Verifier",
        "prompt": "Test Verifier Prompt",
        "tools": ["update_issue_status", "read_file"]
    }))

    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard",
        "seats": {
            "lead_architect": {"name": "lead_architect", "roles": ["lead_architect"]},
            "verifier_seat": {"name": "verifier_seat", "roles": ["integrity_guard"]}
        }
    }))

    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "standard",
        "model": "dummy",
        "temperature": 0.1,
        "timeout": 300
    }))

    (root / "model" / "core" / "epics" / "test_epic.json").write_text(json.dumps({
        "id": "EPIC-01",
        "name": "Test Epic",
        "type": "epic",
        "team": "standard",
        "environment": "standard",
        "description": "A test epic.",
        "architecture_governance": {"idesign": False, "pattern": "Tactical"},
        "issues": [
            {
                "id": "ISSUE-01",
                "summary": "Create sanity file",
                "seat": "lead_architect",
                "priority": "High"
            }
        ]
    }))

    # 3. Patch LocalModelProvider
    dummy_provider = GoldenFlowDummyProvider()
    def mock_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    # 4. Run the engine
    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("test_epic")

    # 5. Assertions
    sanity_file = workspace / "agent_output" / "sanity.txt"
    assert sanity_file.exists()
    assert sanity_file.read_text() == "Orket is Operational"

    issue = await engine.cards.get_by_id("ISSUE-01")
    assert issue.status == "done", f"Expected 'done' after verifier turn, got '{issue.status}'"
    assert dummy_provider.turns >= 2, "Should have taken at least 2 turns (Dev + Verifier)"

@pytest.mark.asyncio
async def test_session_resumption(tmp_path, monkeypatch):
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core").mkdir(parents=True)
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir()
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    
    db_path = str(root / "test_resume.db")

    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail", "vision": "V", "ethos": "E", "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7}, "departments": ["core"]
    }))
    
    # Create required dialects
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "R", "summary": "lead_architect", "type": "utility", "description": "D", "tools": ["update_issue_status", "write_file"]
    }))
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "VERI", "summary": "integrity_guard", "type": "utility", "description": "Test Verifier", "tools": ["update_issue_status", "read_file"]
    }))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({"name": "standard", "seats": {"lead_architect": {"name": "L", "roles": ["lead_architect"]}}}))
        
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}))

    (root / "model" / "core" / "epics" / "resume_epic.json").write_text(json.dumps({
        "id": "EPIC-R", "name": "Resume", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [
            {"id": "I1", "summary": "Done already", "seat": "lead_architect"},
            {"id": "I2", "summary": "Target to resume", "seat": "lead_architect"}
        ]
    }))

    from orket.adapters.storage.sqlite_repositories import SQLiteCardRepository
    cards = SQLiteCardRepository(db_path)
    cards.save({"id": "I1", "summary": "Done already", "seat": "lead_architect", "type": "issue", "priority": "Low", "status": "done", "build_id": "build-resume_epic"})
    
    dummy_provider = GoldenFlowDummyProvider()
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("resume_epic", target_issue_id="I2")

    issue2 = await engine.cards.get_by_id("I2")
    assert issue2.status == "done"
    
    issue1 = await engine.cards.get_by_id("I1")
    assert issue1.status == "done"


