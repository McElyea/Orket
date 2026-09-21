import asyncio
import json

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from tests.helpers.card_completion import text_acceptance
from tests.turn_prompt_utils import extract_turn_prompt_context


class GoldenFlowDummyProvider(LocalModelProvider):
    def __init__(self):
        self.model = "dummy"
        self.timeout = 300
        self.turns = 0

    async def complete(self, messages):
        self.turns += 1
        turn_context = extract_turn_prompt_context(messages)
        active_role = str(turn_context.get("role") or "").strip().lower()
        current_status = str(turn_context.get("current_status") or "").strip().lower()

        if active_role in {"integrity_guard", "verifier_seat"} or current_status == "code_review":
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

@pytest.mark.integration
# Layer: integration
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
        "process_rules": {"small_project_builder_variant": "architect"},
        "departments": ["core"]
    }), encoding="utf-8")

    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name,
            "dsl_format": "JSON",
            "constraints": [],
            "hallucination_guard": "None"
        }), encoding="utf-8")

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "ARCH",
        "summary": "lead_architect",
        "type": "utility",
        "description": "Test Architect",
        "prompt": "Test Prompt",
        "tools": ["write_file", "update_issue_status"]
    }), encoding="utf-8")

    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "VERI",
        "summary": "integrity_guard",
        "type": "utility",
        "description": "Test Verifier",
        "prompt": "Test Verifier Prompt",
        "tools": ["update_issue_status", "read_file"]
    }), encoding="utf-8")
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(json.dumps({
        "id": "REV",
        "summary": "code_reviewer",
        "type": "utility",
        "description": "Test Reviewer",
        "prompt": "Test Reviewer Prompt",
        "tools": ["update_issue_status", "read_file"]
    }), encoding="utf-8")

    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard",
        "seats": {
            "lead_architect": {"name": "lead_architect", "roles": ["lead_architect"]},
            "reviewer_seat": {"name": "reviewer_seat", "roles": ["code_reviewer"]},
            "verifier_seat": {"name": "verifier_seat", "roles": ["integrity_guard"]}
        }
    }), encoding="utf-8")

    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "standard",
        "model": "dummy",
        "temperature": 0.1,
        "timeout": 300
    }), encoding="utf-8")

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
                "priority": "High",
                "params": {"completion_acceptance": text_acceptance("agent_output/sanity.txt", "Orket is Operational", workload_id="sanity-file").model_dump(mode="json")}
            }
        ]
    }), encoding="utf-8")

    # 3. Patch LocalModelProvider
    dummy_provider = GoldenFlowDummyProvider()
    def mock_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    # 4. Run the engine
    async with OrchestrationEngine.open(workspace, department="core", db_path=db_path, config_root=root) as engine:
        try:
            await engine.run_card("test_epic")

            # 5. Assertions
            sanity_file = workspace / "agent_output" / "sanity.txt"
            assert sanity_file.exists()
            assert sanity_file.read_text(encoding="utf-8") == "Orket is Operational"

            issue = await engine.cards.get_by_id("ISSUE-01")
            assert issue.status == "done", f"Expected 'done' after verifier turn, got '{issue.status}'"
            assert dummy_provider.turns >= 2, "Should have taken at least 2 turns (Dev + Verifier)"
        finally:
            await engine.close()

@pytest.mark.integration
# Layer: integration
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
        "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
        "process_rules": {"small_project_builder_variant": "architect"},
        "departments": ["core"]
    }), encoding="utf-8")

    # Create required dialects
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "N"
        }), encoding="utf-8")

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "R", "summary": "lead_architect", "type": "utility", "description": "D", "tools": ["update_issue_status", "write_file"]
    }), encoding="utf-8")
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "VERI", "summary": "integrity_guard", "type": "utility", "description": "Test Verifier", "tools": ["update_issue_status", "read_file"]
    }), encoding="utf-8")
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(json.dumps({
        "id": "REV", "summary": "code_reviewer", "type": "utility", "description": "Reviewer", "tools": ["update_issue_status", "read_file"]
    }), encoding="utf-8")
    (root / "model" / "core" / "teams" / "standard.json").write_text(json.dumps({
        "name": "standard",
        "seats": {
            "lead_architect": {"name": "L", "roles": ["lead_architect"]},
            "reviewer_seat": {"name": "R", "roles": ["code_reviewer"]},
        },
    }), encoding="utf-8")

    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1}), encoding="utf-8")

    (root / "model" / "core" / "epics" / "resume_epic.json").write_text(json.dumps({
        "id": "EPIC-R", "name": "Resume", "type": "epic", "team": "standard", "environment": "standard",
        "architecture_governance": {"idesign": False},
        "issues": [
            {"id": card_id, "summary": "Create sanity file", "seat": "lead_architect",
             "params": {"completion_acceptance": text_acceptance("agent_output/sanity.txt", "Orket is Operational", workload_id="sanity-file").model_dump(mode="json")}}
            for card_id in ("I1", "I2")
        ]
    }), encoding="utf-8")

    dummy_provider = GoldenFlowDummyProvider()
    def mock_init(self, *a, **k):
        self.model = "dummy"
        self.timeout = 300
    monkeypatch.setenv("ORKET_DISABLE_RUNTIME_VERIFIER", "true")
    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", dummy_provider.complete)

    async with OrchestrationEngine.open(workspace, department="core", db_path=db_path, config_root=root) as engine:
        try:
            await engine.cards.save({"id": "I1", "summary": "Create sanity file", "seat": "lead_architect", "build_id": "build-resume_epic",
                                     "params": {"completion_acceptance": text_acceptance("agent_output/sanity.txt", "Orket is Operational", workload_id="sanity-file").model_dump(mode="json")}})
            await asyncio.to_thread((workspace / "agent_output/sanity.txt").write_bytes, b"Orket is Operational")
            service = engine.runtime_context.card_completion
            context = await service.begin_attempt(engine.cards, card_id="I1", run_id="seed-run", attempt_id="seed-attempt")
            evaluation = await service.evaluate_attempt(engine.cards, context)
            original_receipt = await engine.cards.update_status("I1", CardStatus.DONE, completion_request=evaluation.request)
            await engine.run_card("resume_epic", target_issue_id="I2")

            issue2 = await engine.cards.get_by_id("I2")
            assert issue2.status == "done"

            issue1 = await engine.cards.get_by_id("I1")
            assert issue1.status == "done"
            assert await engine.cards.read_completion_receipt("I1") == original_receipt
        finally:
            await engine.close()


