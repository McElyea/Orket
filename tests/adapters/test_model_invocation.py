from pathlib import Path
import json
import pytest
from orket.orchestration.engine import OrchestrationEngine
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.exceptions import ExecutionFailed


class DummyProvider(LocalModelProvider):
    def __init__(self):
        self.model = "dummy"
        self.prompts = []

    async def complete(self, messages):
        # Record all messages content
        for m in messages:
            self.prompts.append(m["content"])
        return ModelResponse(content='{"thought": "test", "tool_calls": []}', raw={"model": "dummy", "total_tokens": 10})


@pytest.mark.asyncio
async def test_model_invocation(monkeypatch, tmp_path):
    # Setup mock assets
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core" / "epics").mkdir(parents=True)
    (root / "model" / "core" / "roles").mkdir(parents=True)
    (root / "model" / "core" / "dialects").mkdir(parents=True)
    (root / "model" / "core" / "teams").mkdir(parents=True)
    (root / "model" / "core" / "environments").mkdir(parents=True)
    
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Test Rail", "vision": "T", "ethos": "T", "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}}, "departments": ["core"]
    }))
    for d in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d}.json").write_text(json.dumps({
            "model_family": d, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "ARCH", "summary": "lead_architect", "type": "utility", "description": "D", "prompt": "P", "tools": []
    }))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard", "seats": {"lead_architect": {"name": "L", "roles": ["lead_architect"]}}
    }))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "S", "model": "dummy", "temperature": 0.1
    }))
    (root / "model" / "core" / "epics" / "test_epic.json").write_text(json.dumps({
        "id": "E1", "name": "Test", "type": "epic", "team": "standard", "environment": "standard",
        "description": "Test description", "issues": [{"id": "I1", "summary": "Task 1", "seat": "lead_architect"}]
    }))

    dummy = DummyProvider()

    def mock_provider_init(self, *args, **kwargs):
        self.model = "dummy"
    
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_provider_init)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy.complete)

    workspace = tmp_path / "session"
    workspace.mkdir()
    db_path = str(tmp_path / "test.db")

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    with pytest.raises(ExecutionFailed, match="No executable candidates while backlog incomplete"):
        await engine.run_card("test_epic")

    assert len(dummy.prompts) > 0, "Model provider was never invoked"
    # Check if any recorded prompt contains our task summary
    found_task = any("Task 1" in p for p in dummy.prompts)
    assert found_task, f"Task summary 'Task 1' not found in any prompt: {dummy.prompts}"

