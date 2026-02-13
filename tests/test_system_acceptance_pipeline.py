from __future__ import annotations

import asyncio
import json

import pytest

from orket.llm import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus
from orket.services.gitea_webhook_handler import GiteaWebhookHandler


class MultiRoleAcceptanceProvider:
    async def complete(self, messages):
        prompt_blob = "\n".join((m.get("content") or "").lower() for m in messages)
        active_seat = None
        active_issue_id = None
        for msg in messages:
            content = msg.get("content") or ""
            if "execution context json:" in content.lower():
                try:
                    payload = content.split("\n", 1)[1] if "\n" in content else ""
                    parsed = json.loads(payload)
                    active_seat = (parsed.get("seat") or "").lower()
                    active_issue_id = (parsed.get("issue_id") or "").lower()
                except (json.JSONDecodeError, TypeError):
                    active_seat = None
                    active_issue_id = None
                break

        # Guard oversight: issue is finalized once it reaches the integrity_guard seat.
        if active_seat == "integrity_guard" or active_issue_id in {"guard-1"} or "integrity_guard" in prompt_blob:
            return ModelResponse(
                content='```json\n{"tool": "update_issue_status", "args": {"status": "done"}}\n```',
                raw={"model": "dummy", "total_tokens": 40},
            )

        # Route by active seat/role first; issue-id fallback handles prompt format drift.
        if active_seat == "requirements_analyst" or active_issue_id == "req-1":
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/requirements.txt", "content": "Program shall sum two integers from CLI args and print result."}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 80},
            )

        if active_seat == "developer" or active_issue_id == "dev-1":
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/main.py", "content": "class SummationApp:\\n    def run(self, args):\\n        a = int(args[0]); b = int(args[1])\\n        print(a + b)\\n\\nif __name__ == \\"__main__\\":\\n    import sys\\n    SummationApp().run(sys.argv[1:])\\n"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 140},
            )

        if active_seat == "architect" or active_issue_id == "arc-1":
            return ModelResponse(
                content='```json\n{"tool": "write_file", "args": {"path": "agent_output/design.txt", "content": "Single class: SummationApp with one run(args) method."}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 90},
            )

        # code_reviewer seat: check outputs then send to guard for final approval.
        if active_seat == "code_reviewer" or active_issue_id == "rev-1":
            return ModelResponse(
                content='```json\n{"tool": "read_file", "args": {"path": "agent_output/requirements.txt"}}\n```\n```json\n{"tool": "read_file", "args": {"path": "agent_output/main.py"}}\n```\n```json\n{"tool": "update_issue_status", "args": {"status": "code_review"}}\n```',
                raw={"model": "dummy", "total_tokens": 120},
            )

        return ModelResponse(content="No-op", raw={"model": "dummy", "total_tokens": 1})


def _patch_dummy_model(monkeypatch, provider):
    def fake_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300

    monkeypatch.setattr(LocalModelProvider, "__init__", fake_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)


def _write_core_assets(root, epic_id: str):
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

    roles = {
        "requirements_analyst": ["write_file", "update_issue_status"],
        "architect": ["write_file", "update_issue_status"],
        "developer": ["write_file", "update_issue_status"],
        "code_reviewer": ["read_file", "update_issue_status"],
        "integrity_guard": ["read_file", "update_issue_status"],
    }
    for role_name, tools in roles.items():
        (root / "model" / "core" / "roles" / f"{role_name}.json").write_text(
            json.dumps(
                {
                    "id": role_name.upper(),
                    "summary": role_name,
                    "type": "utility",
                    "description": role_name,
                    "tools": tools,
                }
            ),
            encoding="utf-8",
        )

    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "requirements_analyst": {"name": "Req", "roles": ["requirements_analyst"]},
                    "architect": {"name": "Arch", "roles": ["architect"]},
                    "developer": {"name": "Dev", "roles": ["developer"]},
                    "code_reviewer": {"name": "CR", "roles": ["code_reviewer"]},
                    "integrity_guard": {"name": "Guard", "roles": ["integrity_guard"]},
                },
            }
        ),
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
                "name": "Acceptance Pipeline",
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Role-pipeline acceptance",
                "architecture_governance": {"idesign": False, "pattern": "Tactical"},
                "issues": [
                    {"id": "REQ-1", "summary": "Write requirements", "seat": "requirements_analyst", "priority": "High"},
                    {
                        "id": "ARC-1",
                        "summary": "Design one-class architecture",
                        "seat": "architect",
                        "priority": "High",
                        "depends_on": ["REQ-1"],
                    },
                    {
                        "id": "DEV-1",
                        "summary": "Implement based on design",
                        "seat": "developer",
                        "priority": "High",
                        "depends_on": ["ARC-1"],
                    },
                    {
                        "id": "REV-1",
                        "summary": "Review against requirements",
                        "seat": "code_reviewer",
                        "priority": "High",
                        "depends_on": ["DEV-1"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_system_acceptance_role_pipeline_with_guard(tmp_path, monkeypatch):
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_pipeline.db")

    _write_core_assets(root, epic_id="acceptance_pipeline")
    _patch_dummy_model(monkeypatch, MultiRoleAcceptanceProvider())

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_pipeline")

    for issue_id in ("REQ-1", "ARC-1", "DEV-1", "REV-1"):
        issue = await engine.cards.get_by_id(issue_id)
        assert issue.status == CardStatus.DONE, f"{issue_id} did not reach DONE"

    assert (workspace / "agent_output" / "requirements.txt").exists()
    assert (workspace / "agent_output" / "design.txt").exists()
    assert (workspace / "agent_output" / "main.py").exists()


@pytest.mark.asyncio
async def test_webhook_opened_event_triggers_issue_code_review(monkeypatch, tmp_path):
    monkeypatch.setenv("GITEA_ADMIN_PASSWORD", "test-pass")

    captured = {"updated_to": None, "run_card_id": None}
    original_create_task = asyncio.create_task
    scheduled_tasks = []

    class FakeCards:
        async def update_status(self, issue_id, status):
            captured["updated_to"] = (issue_id, status)

    class FakeEngine:
        def __init__(self, workspace):
            self.workspace = workspace
            self.cards = FakeCards()

        async def run_card(self, issue_id):
            captured["run_card_id"] = issue_id
            return {"ok": True}

    def _fake_create_task(coro):
        task = original_create_task(coro)
        scheduled_tasks.append(task)
        return task

    monkeypatch.setattr("orket.orchestration.engine.OrchestrationEngine", FakeEngine, raising=False)
    monkeypatch.setattr("asyncio.create_task", _fake_create_task, raising=False)

    handler = GiteaWebhookHandler(workspace=tmp_path)
    payload = {
        "action": "opened",
        "pull_request": {"number": 42, "title": "[ISSUE-ABC1] tiny program"},
        "repository": {"name": "demo", "owner": {"login": "Orket"}},
    }
    result = await handler.handle_webhook("pull_request", payload)
    if scheduled_tasks:
        await asyncio.gather(*scheduled_tasks)
    await handler.close()

    assert result["status"] == "success"
    assert captured["updated_to"] == ("ISSUE-ABC1", "code_review")
    assert captured["run_card_id"] == "ISSUE-ABC1"
