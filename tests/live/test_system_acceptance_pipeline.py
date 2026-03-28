from __future__ import annotations

import asyncio
import json
import os

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.orchestration.engine import OrchestrationEngine
from orket.runtime.live_acceptance_assets import write_core_acceptance_assets
from orket.schema import CardStatus
from orket.adapters.vcs.gitea_webhook_handler import GiteaWebhookHandler
from tests.live.run_summary_support import read_validated_run_summary

pytestmark = pytest.mark.end_to_end


def _safe_console(text: str) -> str:
    return text.encode("ascii", errors="backslashreplace").decode("ascii")


def _read_json(path) -> dict:
    return json.loads(path.read_bytes().decode("utf-8"))


def _read_text(path) -> str:
    return path.read_bytes().decode("utf-8")


def _run_roots(workspace):
    runs_root = workspace / "runs"
    if not runs_root.exists():
        return []
    return sorted(path for path in runs_root.iterdir() if path.is_dir())


class MultiRoleAcceptanceProvider:
    async def complete(self, messages):
        active_seat = None
        active_issue_id = None
        required_read_paths: list[str] = []
        required_write_paths: list[str] = []
        required_statuses: list[str] = []
        missing_required_read_paths: set[str] = set()
        for msg in messages:
            content = msg.get("content") or ""
            if "execution context json:" in content.lower():
                try:
                    payload = content.split("\n", 1)[1] if "\n" in content else ""
                    parsed = json.loads(payload)
                    active_seat = (parsed.get("seat") or "").lower()
                    active_issue_id = (parsed.get("issue_id") or "").lower()
                    required_read_paths = [
                        str(path).strip()
                        for path in (parsed.get("required_read_paths") or [])
                        if str(path).strip()
                    ]
                    required_write_paths = [
                        str(path).strip()
                        for path in (parsed.get("required_write_paths") or [])
                        if str(path).strip()
                    ]
                    required_statuses = [
                        str(status).strip()
                        for status in (parsed.get("required_statuses") or [])
                        if str(status).strip()
                    ]
                    missing_required_read_paths = {
                        str(path).strip()
                        for path in (parsed.get("missing_required_read_paths") or [])
                        if str(path).strip()
                    }
                except (json.JSONDecodeError, TypeError):
                    active_seat = None
                    active_issue_id = None
                    required_read_paths = []
                    required_write_paths = []
                    required_statuses = []
                    missing_required_read_paths = set()
                break

        def _render_calls(calls: list[dict]) -> str:
            return "\n".join(f"```json\n{json.dumps(call)}\n```" for call in calls)

        def _status_or(default_status: str) -> str:
            return required_statuses[0] if required_statuses else default_status

        readable_paths = [path for path in required_read_paths if path not in missing_required_read_paths]

        # Route by active seat/role first; issue-id fallback handles prompt format drift.
        if active_seat == "requirements_analyst" or (not active_seat and active_issue_id == "req-1"):
            target_path = required_write_paths[0] if required_write_paths else "agent_output/requirements.txt"
            calls = [
                {
                    "tool": "write_file",
                    "args": {
                        "path": target_path,
                        "content": "Program shall sum two integers from CLI args and print result.",
                    },
                },
                {"tool": "update_issue_status", "args": {"status": _status_or("code_review")}},
            ]
            return ModelResponse(
                content=_render_calls(calls),
                raw={"model": "dummy", "total_tokens": 80},
            )

        if active_seat == "coder" or (not active_seat and active_issue_id == "cod-1"):
            target_path = required_write_paths[0] if required_write_paths else "agent_output/main.py"
            calls = [
                {
                    "tool": "write_file",
                    "args": {
                        "path": target_path,
                        "content": (
                            "class SummationApp:\n"
                            "    def run(self, args):\n"
                            "        a = int(args[0]); b = int(args[1])\n"
                            "        print(a + b)\n\n"
                            'if __name__ == "__main__":\n'
                            "    import sys\n"
                            "    SummationApp().run(sys.argv[1:])\n"
                        ),
                    },
                },
                {"tool": "update_issue_status", "args": {"status": _status_or("code_review")}},
            ]
            return ModelResponse(
                content=_render_calls(calls),
                raw={"model": "dummy", "total_tokens": 140},
            )

        if active_seat == "architect" or (not active_seat and active_issue_id == "arc-1"):
            target_path = required_write_paths[0] if required_write_paths else "agent_output/design.txt"
            calls = [{"tool": "read_file", "args": {"path": path}} for path in readable_paths]
            calls.append(
                {
                    "tool": "write_file",
                    "args": {
                        "path": target_path,
                        "content": json.dumps(
                            {
                                "recommendation": "monolith",
                                "frontend_framework": "vue",
                                "confidence": 0.88,
                                "evidence": {
                                    "estimated_domains": 1,
                                    "external_integrations": 0,
                                    "independent_scaling_needs": "low",
                                    "deployment_complexity": "low",
                                    "team_parallelism": "single",
                                    "operational_maturity": "low",
                                },
                                "notes": "Single class SummationApp with one run(args) method.",
                            }
                        ),
                    },
                }
            )
            calls.append({"tool": "update_issue_status", "args": {"status": _status_or("code_review")}})
            return ModelResponse(
                content=_render_calls(calls),
                raw={"model": "dummy", "total_tokens": 90},
            )

        # code_reviewer seat: check outputs then send to guard for final approval.
        if active_seat == "code_reviewer" or (not active_seat and active_issue_id == "rev-1"):
            review_paths = readable_paths or ["agent_output/requirements.txt", "agent_output/main.py"]
            calls = [{"tool": "read_file", "args": {"path": path}} for path in review_paths]
            calls.append({"tool": "update_issue_status", "args": {"status": _status_or("code_review")}})
            return ModelResponse(
                content=_render_calls(calls),
                raw={"model": "dummy", "total_tokens": 120},
            )

        if active_seat == "integrity_guard" or active_issue_id in {"guard-1"}:
            calls = [{"tool": "read_file", "args": {"path": path}} for path in readable_paths]
            calls.append({"tool": "update_issue_status", "args": {"status": _status_or("done")}})
            return ModelResponse(
                content=_render_calls(calls),
                raw={"model": "dummy", "total_tokens": 40},
            )

        return ModelResponse(content="No-op", raw={"model": "dummy", "total_tokens": 1})


def _patch_dummy_model(monkeypatch, provider):
    def fake_init(self, *args, **kwargs):
        self.model = "dummy"
        self.timeout = 300

    monkeypatch.setattr(LocalModelProvider, "__init__", fake_init)
    monkeypatch.setattr(LocalModelProvider, "complete", provider.complete)


def _write_core_assets(root, epic_id: str, environment_model: str = "dummy"):
    write_core_acceptance_assets(root, epic_id=epic_id, environment_model=environment_model)


@pytest.mark.asyncio
async def test_system_acceptance_role_pipeline_with_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
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

    for issue_id in ("REQ-1", "ARC-1", "COD-1", "REV-1"):
        issue = await engine.cards.get_by_id(issue_id)
        assert issue.status == CardStatus.DONE, f"{issue_id} did not reach DONE"

    assert (workspace / "agent_output" / "requirements.txt").exists()
    assert (workspace / "agent_output" / "design.txt").exists()
    assert (workspace / "agent_output" / "main.py").exists()
    runtime_report = workspace / "agent_output" / "verification" / "runtime_verification.json"
    assert runtime_report.exists(), "runtime verification artifact missing in canonical acceptance run."
    runtime_payload = json.loads(runtime_report.read_text(encoding="utf-8"))
    assert isinstance(runtime_payload.get("ok"), bool)
    assert isinstance(runtime_payload.get("command_results"), list)
    checkpoint_paths = list((workspace / "observability").rglob("checkpoint.json"))
    assert checkpoint_paths, "Expected turn checkpoint artifacts for acceptance run."
    for checkpoint_path in checkpoint_paths:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        metadata = payload.get("prompt_metadata", {})
        assert isinstance(metadata, dict)
        assert metadata.get("resolver_policy")
        assert metadata.get("selection_policy")


@pytest.mark.asyncio
async def test_system_acceptance_role_pipeline_with_guard_live(tmp_path, monkeypatch):
    if os.getenv("ORKET_LIVE_ACCEPTANCE", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("Set ORKET_LIVE_ACCEPTANCE=1 to run live acceptance with Ollama.")

    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    model_name = os.getenv("ORKET_LIVE_MODEL", "llama3.2:3b")

    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "acceptance_pipeline_live.db")

    _write_core_assets(root, epic_id="acceptance_pipeline_live", environment_model=model_name)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("acceptance_pipeline_live")

    req_issue = await engine.cards.get_by_id("REQ-1")
    arc_issue = await engine.cards.get_by_id("ARC-1")
    cod_issue = await engine.cards.get_by_id("COD-1")
    rev_issue = await engine.cards.get_by_id("REV-1")

    requirements_path = workspace / "agent_output" / "requirements.txt"
    design_path = workspace / "agent_output" / "design.txt"
    code_path = workspace / "agent_output" / "main.py"
    runtime_report = workspace / "agent_output" / "verification" / "runtime_verification.json"

    requirements_text = _read_text(requirements_path) if requirements_path.exists() else ""
    design_text = _read_text(design_path) if design_path.exists() else ""
    code_text = _read_text(code_path) if code_path.exists() else ""

    print(f"[live] model={model_name}")
    print(f"[live] REQ-1 status={req_issue.status}")
    print(f"[live] ARC-1 status={arc_issue.status}")
    print(f"[live] COD-1 status={cod_issue.status}")
    print(f"[live] REV-1 status={rev_issue.status}")
    print("[live] requirements.txt")
    print(_safe_console(requirements_text))
    print("[live] design.txt")
    print(_safe_console(design_text))
    print("[live] main.py")
    print(_safe_console(code_text))

    assert req_issue.status == CardStatus.DONE, "REQ-1 must complete DONE in canonical chain"
    assert arc_issue.status == CardStatus.DONE, "ARC-1 must complete DONE in canonical chain"
    assert cod_issue.status == CardStatus.DONE, "COD-1 must complete DONE in canonical chain"
    assert rev_issue.status == CardStatus.DONE, "REV-1 must complete DONE in canonical chain"

    assert requirements_path.exists(), "requirements.txt not produced for completed REQ-1"
    assert design_path.exists(), "design.txt not produced for completed ARC-1"
    assert code_path.exists(), "main.py not produced for completed COD-1"
    assert runtime_report.exists(), "runtime_verification.json missing for live acceptance run"

    runtime_payload = _read_json(runtime_report)
    assert isinstance(runtime_payload.get("ok"), bool)
    assert isinstance(runtime_payload.get("command_results"), list)

    run_roots = _run_roots(workspace)
    assert len(run_roots) == 1, "Expected exactly one fresh run directory for live acceptance proof."
    run_root = run_roots[0]
    run_summary_path = run_root / "run_summary.json"
    assert run_summary_path.exists(), "run_summary.json missing from live run root"
    run_summary = read_validated_run_summary(run_summary_path)
    assert run_summary.get("run_id") == run_root.name
    assert run_summary.get("status") == "done"
    assert "workspace_state_snapshot" in list(run_summary.get("artifact_ids") or [])

    run_ledger_mode = os.getenv("ORKET_RUN_LEDGER_MODE", "").strip().lower()
    if run_ledger_mode in {"append_only", "append_only_protocol", "dual", "dual_write", "mirror", "protocol"}:
        assert (run_root / "events.log").exists(), "events.log missing for protocol-capable live run"

    print(f"[live] run_id={run_root.name}")
    print(f"[live] run_root={run_root}")


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

