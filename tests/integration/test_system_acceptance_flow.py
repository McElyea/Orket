from __future__ import annotations

import json

import pytest

from orket.exceptions import ExecutionFailed
from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus


class AcceptanceProvider:
    def __init__(self, mode: str):
        self.mode = mode

    async def complete(self, messages):
        if self.mode == "approve":
            system_prompt = messages[0]["content"]
            if "CODE REVIEW" in system_prompt or "integrity_guard" in system_prompt.lower():
                return ModelResponse(
                    content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                    raw={"model": "dummy", "total_tokens": 50},
                )
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/acceptance.txt", "content": "ok"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 80},
            )

        if self.mode == "reject":
            system_prompt = messages[0]["content"]
            if "CODE REVIEW" in system_prompt or "integrity_guard" in system_prompt.lower():
                return ModelResponse(
                    content='{"rationale":"Insufficient acceptance criteria coverage.","violations":["missing acceptance criteria"],"remediation_actions":["Document explicit acceptance criteria before merge."]}\n```json\n{"tool": "update_issue_status", "args": {"status": "blocked", "wait_reason": "review"}}\n```',
                    raw={"model": "dummy", "total_tokens": 50},
                )
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/acceptance.txt", "content": "ok"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 80},
            )

        # Illegal state transition path: coder attempts direct READY -> DONE.
        return ModelResponse(
            content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
            raw={"model": "dummy", "total_tokens": 40},
        )


def _build_assets(root, *, with_guard: bool, epic_id: str):
    (root / "config").mkdir()
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir(parents=True, exist_ok=True)

    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Acceptance Org",
                "vision": "Test",
                "ethos": "Test",
                "branding": {"design_dos": []},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "departments": ["core"],
            }
        ),
        encoding="utf-8",
    )

    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(
            json.dumps({"model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "None"}),
            encoding="utf-8",
        )

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": "Architect",
                "tools": ["write_file", "update_issue_status"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(
        json.dumps(
            {
                "id": "VERI",
                "summary": "integrity_guard",
                "type": "utility",
                "description": "Verifier",
                "tools": ["update_issue_status", "read_file"],
            }
        ),
        encoding="utf-8",
    )

    seats = {"lead_architect": {"name": "Lead", "roles": ["lead_architect"]}}
    if with_guard:
        seats["verifier_seat"] = {"name": "Verifier", "roles": ["integrity_guard"]}
    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps({"name": "standard", "seats": seats}),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "dummy", "temperature": 0.1, "timeout": 300}),
        encoding="utf-8",
    )

    (root / "model" / "core" / "epics" / f"{epic_id}.json").write_text(
        json.dumps(
            {
                "id": epic_id,
                "name": "System Acceptance Epic",
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Acceptance-level flow test",
                "architecture_governance": {"idesign": False, "pattern": "Tactical"},
                "issues": [{"id": "ISSUE-A", "summary": "Run acceptance flow", "seat": "lead_architect", "priority": "High"}],
            }
        ),
        encoding="utf-8",
    )


def _patch_provider(monkeypatch, provider):
    def mock_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300

    monkeypatch.setattr(LocalModelProvider, "__init__", mock_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)


@pytest.mark.asyncio
async def test_system_acceptance_guard_approves_actions(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_approve.db")

    _build_assets(root, with_guard=True, epic_id="acceptance_approve")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="approve"))

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_approve")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.DONE
    assert (workspace / "agent_output" / "acceptance.txt").exists()
    log_blob = (workspace / "orket.log").read_text(encoding="utf-8")
    assert '"event": "guard_approved"' in log_blob
    assert '"event": "guard_review_payload"' in log_blob


@pytest.mark.asyncio
async def test_system_acceptance_guard_rejects_actions(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_reject.db")

    _build_assets(root, with_guard=True, epic_id="acceptance_reject")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="reject"))

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_reject")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.BLOCKED
    log_blob = (workspace / "orket.log").read_text(encoding="utf-8")
    assert '"event": "guard_rejected"' in log_blob
    assert '"event": "guard_payload_invalid"' not in log_blob


@pytest.mark.asyncio
async def test_system_acceptance_guard_blocks_illegal_transition(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_block.db")

    _build_assets(root, with_guard=False, epic_id="acceptance_block")
    _patch_provider(monkeypatch, AcceptanceProvider(mode="block"))

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    with pytest.raises(ExecutionFailed):
        await engine.run_card("acceptance_block")

    issue = await engine.cards.get_by_id("ISSUE-A")
    assert issue.status == CardStatus.BLOCKED
    assert (workspace / "agent_output" / "policy_violation_ISSUE-A.json").exists()

