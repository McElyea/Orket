import pytest
import json
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.llm import LocalModelProvider, ModelResponse
from orket.exceptions import ExecutionFailed

class MockiDesignProvider(LocalModelProvider):
    def __init__(self, bad_path=False):
        self.model = "dummy"
        self.bad_path = bad_path
        self.timeout = 300

    async def complete(self, messages):
        path = "messy_file.py" if self.bad_path else "engines/logic.py"
        content = f"""```json
{{"tool": "write_file", "args": {{"path": "{path}", "content": "print(1)"}}}}
```
```json
{{"tool": "update_issue_status", "args": {{"status": "code_review"}}}}
```"""
        return ModelResponse(content=content, raw={"model": "dummy", "total_tokens": 10})

@pytest.mark.asyncio
async def test_complexity_gate_violation(tmp_path):
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail", "vision": "V", "ethos": "E",
        "architecture": {"idesign_threshold": 2}, "departments": ["core"]
    }))
    
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard", "seats": {}
    }))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "standard", "model": "dummy", "temperature": 0.1
    }))
    
    # Epic with 3 issues but idesign: false
    (root / "model" / "core" / "epics" / "messy_epic.json").write_text(json.dumps({
        "id": "EPIC-M", "name": "Messy", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [{"id": "1", "seat": "S", "summary": "S"}, {"id": "2", "seat": "S", "summary": "S"}, {"id": "3", "seat": "S", "summary": "S"}]
    }))
    
    engine = OrchestrationEngine(root / "ws", config_root=root)
    with pytest.raises(ExecutionFailed) as exc:
        await engine.run_card("messy_epic")
    assert "Complexity Gate Violation" in str(exc.value)

@pytest.mark.asyncio
async def test_idesign_structural_violation(tmp_path, monkeypatch):
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "roles").mkdir(parents=True)
    (root / "model" / "core" / "dialects").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    db_path = str(root / "test.db")

    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Vibe Rail", "vision": "V", "ethos": "E",
        "architecture": {"idesign_threshold": 10, "cicd_rules": []}, "departments": ["core"]
    }))
    
    # Create required dialects
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))

    (root / "model" / "core" / "epics" / "strict_epic.json").write_text(json.dumps({
        "id": "EPIC-S", "name": "Strict", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": True},
        "issues": [{"id": "ISSUE-1", "seat": "lead_architect", "summary": "Task"}]
    }))
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({"id": "R", "summary": "lead_architect", "description": "D", "tools": ["write_file", "update_issue_status"]}))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({"name": "standard", "seats": {"lead_architect": {"name": "L", "roles": ["lead_architect"]}}}))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}))

    bad_provider = MockiDesignProvider(bad_path=True)
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", bad_provider.complete)

    engine = OrchestrationEngine(root / "ws", db_path=db_path, config_root=root)
    
    with pytest.raises(ExecutionFailed) as exc:
        await engine.run_card("strict_epic")
    assert "iDesign Violation" in str(exc.value)
