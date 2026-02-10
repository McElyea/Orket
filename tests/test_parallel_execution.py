import pytest
import json
import asyncio
import time
from pathlib import Path
from orket.orchestration.engine import OrchestrationEngine
from orket.llm import LocalModelProvider, ModelResponse
from orket.schema import CardStatus

class ParallelDummyProvider(LocalModelProvider):
    def __init__(self):
        self.model = "dummy"
        self.timeout = 300
        self.turns = 0
        self.active_calls = 0
        self.max_parallel = 0

    async def complete(self, messages):
        self.active_calls += 1
        self.max_parallel = max(self.max_parallel, self.active_calls)
        self.turns += 1
        
        # Artificial delay to simulate LLM latency and allow parallelism to be visible
        await asyncio.sleep(0.5)
        
        system_prompt = messages[0]["content"]
        
        if "integrity_guard" in system_prompt.lower():
            self.active_calls -= 1
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 50}
            )
        else:
            self.active_calls -= 1
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 100}
            )

@pytest.mark.asyncio
async def test_parallel_execution_throughput(tmp_path, monkeypatch):
    """
    Verifies that independent issues are executed in parallel.
    We create 3 independent issues. If running in parallel, they should finish 
    their first turns in ~0.5s instead of 1.5s.
    """
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core").mkdir(parents=True)
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir()
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    
    db_path = str(root / "test_parallel.db")

    # Mock Assets
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Parallel Corp", "vision": "V", "ethos": "E", "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 10}, "departments": ["core"]
    }))
    
    # Create an empty user_settings to avoid loading from host machine
    (root / "user_settings.json").write_text(json.dumps({}))
    
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "R1", "summary": "lead_architect", "type": "utility", "description": "D", "tools": ["update_issue_status"]
    }))
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "R2", "summary": "integrity_guard", "type": "utility", "description": "V", "tools": ["update_issue_status"]
    }))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard", 
        "seats": {
            "lead_architect": {"name": "L", "roles": ["lead_architect"]},
            "verifier_seat": {"name": "V", "roles": ["integrity_guard"]}
        }
    }))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "standard", "model": "dummy", "temperature": 0.1
    }))

    # Create an Epic with 3 independent issues
    (root / "model" / "core" / "epics" / "parallel_epic.json").write_text(json.dumps({
        "id": "EPIC-P", "name": "Parallel", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [
            {"id": "P1", "summary": "Task 1", "seat": "lead_architect", "depends_on": []},
            {"id": "P2", "summary": "Task 2", "seat": "lead_architect", "depends_on": []},
            {"id": "P3", "summary": "Task 3", "seat": "lead_architect", "depends_on": []}
        ]
    }))

    dummy_provider = ParallelDummyProvider()
    monkeypatch.setattr(LocalModelProvider, "__init__", lambda *a, **k: None)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    
    start_time = time.time()
    await engine.run_epic("parallel_epic")
    end_time = time.time()

    total_duration = end_time - start_time
    
    # Assertions
    # 3 tasks * 2 turns (Dev -> Review, Verifier -> Done) = 6 turns total
    # If parallelized: 
    # Tick 1: 3 Dev turns in parallel (~0.5s)
    # Tick 2: 3 Verifier turns in parallel (~0.5s)
    # Total roughly 1.0s - 1.2s
    # If serial: 6 turns * 0.5s = 3.0s
    
    print(f"Total Duration: {total_duration:.2f}s")
    print(f"Max Parallel Calls: {dummy_provider.max_parallel}")
    
    assert dummy_provider.max_parallel > 1, "Should have executed at least some calls in parallel"
    assert total_duration < 2.5, f"Expected duration < 2.5s for parallel execution, got {total_duration:.2f}s"
    
    p1 = await engine.cards.get_by_id("P1")
    p2 = await engine.cards.get_by_id("P2")
    p3 = await engine.cards.get_by_id("P3")
    
    assert p1.status == "done"
    assert p2.status == "done"
    assert p3.status == "done"

@pytest.mark.asyncio
async def test_dependency_chain_serial(tmp_path, monkeypatch):
    """
    Verifies that dependent issues are still executed serially.
    P1 -> P2 -> P3
    """
    root = tmp_path
    (root / "config").mkdir()
    (root / "model" / "core").mkdir(parents=True)
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir()
    
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    
    db_path = str(root / "test_serial.db")

    # Mock Assets (minimal)
    (root / "config" / "organization.json").write_text(json.dumps({
        "name": "Serial Corp", "vision": "V", "ethos": "E", "branding": {"design_dos": []},
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 10}, "departments": ["core"]
    }))
    
    # Create an empty user_settings to avoid loading from host machine
    (root / "user_settings.json").write_text(json.dumps({}))
    
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }))

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "R1", "summary": "lead_architect", "type": "utility", "description": "D", "tools": ["update_issue_status"]
    }))
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "R2", "summary": "integrity_guard", "type": "utility", "description": "V", "tools": ["update_issue_status"]
    }))
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard", "seats": {"lead_architect": {"name": "L", "roles": ["lead_architect"]}, "verifier_seat": {"name": "V", "roles": ["integrity_guard"]}}
    }))
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}))

    # Create an Epic with dependency chain: P1 -> P2 -> P3
    (root / "model" / "core" / "epics" / "chain_epic.json").write_text(json.dumps({
        "id": "EPIC-C", "name": "Chain", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [
            {"id": "C1", "summary": "Task 1", "seat": "lead_architect", "depends_on": []},
            {"id": "C2", "summary": "Task 2", "seat": "lead_architect", "depends_on": ["C1"]},
            {"id": "C3", "summary": "Task 3", "seat": "lead_architect", "depends_on": ["C2"]}
        ]
    }))

    dummy_provider = ParallelDummyProvider()
    monkeypatch.setattr(LocalModelProvider, "__init__", lambda *a, **k: None)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    
    await engine.run_epic("chain_epic")
    
    # In a chain, they should NEVER run in parallel
    assert dummy_provider.max_parallel == 1, "Chain should have been executed serially"
    
    c3 = await engine.cards.get_by_id("C3")
    assert c3.status == "done"
