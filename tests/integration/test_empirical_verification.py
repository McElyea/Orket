import pytest
import json
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.schema import CardStatus

FIXTURE_CONTENT = """
def verify(input_data):
    if input_data.get("value") == 42:
        return 42
    return 0
"""

@pytest.mark.asyncio
async def test_empirical_verification_pass(tmp_path, monkeypatch):
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "roles").mkdir(parents=True)
    (root / "model" / "core" / "dialects").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "verification").mkdir()
    
    # 1. Create Fixture File in verification/ directory
    fixture_file = workspace / "verification" / "test_fixture.py"
    fixture_file.write_text(FIXTURE_CONTENT)

    # 2. Create assets
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail", "vision": "V", "ethos": "E",
        "architecture": {"idesign_threshold": 7, "cicd_rules": []},
        "process_rules": {"small_project_builder_variant": "architect"},
        "departments": ["core"]
    }))
    for d in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d}.json").write_text(json.dumps({"model_family": d, "dsl_format": "J", "constraints": [], "hallucination_guard": "N"}))
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({"id": "R", "summary": "lead_architect", "description": "D", "tools": ["update_issue_status", "write_file"]}))
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({"id": "V", "summary": "integrity_guard", "description": "V", "tools": ["update_issue_status"]}))
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(json.dumps({"id": "C", "summary": "code_reviewer", "description": "R", "tools": ["update_issue_status"]}))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard", 
        "seats": {
            "lead_architect": {"name": "L", "roles": ["lead_architect"]},
            "reviewer_seat": {"name": "R", "roles": ["code_reviewer"]},
            "verifier": {"name": "V", "roles": ["integrity_guard"]}
        }
    }))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}))

    # Epic with Verification Scenarios
    (root / "model" / "core" / "epics" / "verify_epic.json").write_text(json.dumps({
        "id": "EPIC-V", "name": "Verify", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [
            {
                "id": "I1", "summary": "Task", "seat": "lead_architect",
                "verification": {
                    "fixture_path": "verification/test_fixture.py",
                    "scenarios": [
                        {"description": "Success Case", "input_data": {"value": 42}, "expected_output": 42}
                    ]
                }
            }
        ]
    }))

    # 3. Mock Provider
    class MockProvider(LocalModelProvider):
        def __init__(self): 
            self.model = "dummy"
            self.timeout = 300
            self.turns = 0
        async def complete(self, messages):
            self.turns += 1
            if self.turns == 1: # Dev turn
                content = """```json
{"tool": "update_issue_status", "args": {"status": "code_review"}}
```"""
                return ModelResponse(content=content, raw={"model": "dummy", "total_tokens": 10})
            else: # Verifier turn
                content = """```json
{"tool": "update_issue_status", "args": {"status": "done"}}
```"""
                return ModelResponse(content=content, raw={"model": "dummy", "total_tokens": 10})

    p = MockProvider()
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", p.complete)

    # 4. Run
    engine = OrchestrationEngine(workspace, db_path=str(root/"test.db"), config_root=root)
    await engine.run_card("verify_epic")

    # 5. Assertions
    issue = await engine.cards.get_by_id("I1")
    assert issue.status == "done"
    
    # Check that verification result was persisted
    # Note: SQLiteCardRepository returns a dict where complex types are in 'verification' key
    # after being loaded from 'verification_json'
    assert hasattr(issue, "verification")
    v = issue.verification
    assert v["last_run"]["passed"] == 1
    assert v["scenarios"][0]["status"] == "pass"

