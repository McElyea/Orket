from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from orket.adapters.llm import local_model_provider as local_model_provider_module
from orket.orchestration.engine import OrchestrationEngine
from orket.schema import CardStatus


def _write_runtime_assets(root: Path) -> None:
    (root / "config").mkdir()
    for directory in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / directory).mkdir(parents=True, exist_ok=True)

    (root / "config" / "organization.json").write_text(
        json.dumps(
            {
                "name": "Runtime Contract Org",
                "vision": "Runtime truth",
                "ethos": "Runtime truth",
                "branding": {"design_dos": []},
                "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
                "process_rules": {"small_project_builder_variant": "architect"},
                "departments": ["core"],
            }
        ),
        encoding="utf-8",
    )

    for dialect in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{dialect}.json").write_text(
            json.dumps(
                {
                    "model_family": dialect,
                    "dsl_format": "JSON",
                    "constraints": [],
                    "hallucination_guard": "N",
                }
            ),
            encoding="utf-8",
        )

    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(
        json.dumps(
            {
                "id": "ARCH",
                "summary": "lead_architect",
                "type": "utility",
                "description": "Build",
                "tools": ["write_file", "read_file", "update_issue_status"],
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
                "description": "Verify",
                "tools": ["update_issue_status", "read_file"],
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "roles" / "code_reviewer.json").write_text(
        json.dumps(
            {
                "id": "REV",
                "summary": "code_reviewer",
                "type": "utility",
                "description": "Review",
                "tools": ["update_issue_status", "read_file"],
            }
        ),
        encoding="utf-8",
    )

    (root / "model" / "core" / "teams" / "standard.json").write_text(
        json.dumps(
            {
                "name": "standard",
                "seats": {
                    "lead_architect": {"name": "Lead", "roles": ["lead_architect"]},
                    "reviewer_seat": {"name": "Reviewer", "roles": ["code_reviewer"]},
                    "verifier_seat": {"name": "Guard", "roles": ["integrity_guard"]},
                },
            }
        ),
        encoding="utf-8",
    )
    (root / "model" / "core" / "environments" / "standard.json").write_text(
        json.dumps({"name": "standard", "model": "qwen3.5-4b", "temperature": 0.1, "timeout": 300}),
        encoding="utf-8",
    )
    (root / "model" / "core" / "epics" / "runtime_truth_epic.json").write_text(
        json.dumps(
            {
                "id": "runtime_truth_epic",
                "name": "Runtime Truth Epic",
                "type": "epic",
                "team": "standard",
                "environment": "standard",
                "description": "Validates runtime provider and tool execution seams.",
                "architecture_governance": {"idesign": False, "pattern": "Tactical"},
                "issues": [{"id": "ISSUE-1", "summary": "Task 1", "seat": "lead_architect"}],
            }
        ),
        encoding="utf-8",
    )


def _seat_from_messages(messages: list[dict[str, Any]]) -> str:
    marker = "Execution Context JSON:\n"
    decoder = json.JSONDecoder()
    for message in messages:
        content = str((message or {}).get("content") or "")
        if marker not in content:
            continue
        payload_text = content.split(marker, 1)[1]
        try:
            parsed, _ = decoder.raw_decode(payload_text.lstrip())
        except (json.JSONDecodeError, TypeError, ValueError):
            return ""
        if isinstance(parsed, dict):
            return str(parsed.get("seat") or "").strip().lower()
        return ""
    return ""


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.closed = False

    async def post(self, path: str, headers: dict[str, str], **kwargs: Any) -> httpx.Response:
        payload = dict(kwargs.get("json") or {})
        lower_headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.requests.append({"path": path, "headers": lower_headers, "payload": payload})

        seat = _seat_from_messages(list(payload.get("messages") or []))
        if seat in {"integrity_guard", "verifier_seat"}:
            envelope = {
                "content": "",
                "tool_calls": [{"tool": "update_issue_status", "args": {"status": "done"}}],
            }
        else:
            envelope = {
                "content": "",
                "tool_calls": [
                    {"tool": "write_file", "args": {"path": "agent_output/runtime_truth.txt", "content": "runtime-ok"}},
                    {"tool": "read_file", "args": {"path": "agent_output/runtime_truth.txt"}},
                    {"tool": "update_issue_status", "args": {"status": "code_review"}},
                ],
            }

        request = httpx.Request("POST", f"http://127.0.0.1:1234/v1{path}")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-runtime-truth",
                "choices": [{"message": {"role": "assistant", "content": json.dumps(envelope)}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
            headers={"content-type": "application/json"},
            request=request,
        )

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_model_invocation_uses_runtime_provider_and_executes_real_tools(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path
    workspace = root / "workspace"
    workspace.mkdir()
    (workspace / "agent_output").mkdir()
    (workspace / "verification").mkdir()
    db_path = str(root / "runtime_truth.db")

    _write_runtime_assets(root)

    fake_client = _FakeOpenAIClient()
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("ORKET_PROTOCOL_GOVERNED_ENABLED", "true")
    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "enforce")
    monkeypatch.setattr(local_model_provider_module.httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    engine = OrchestrationEngine(workspace, department="core", db_path=db_path, config_root=root)
    await engine.run_card("runtime_truth_epic", session_id="runtime-session-1")

    issue = await engine.cards.get_by_id("ISSUE-1")
    assert issue.status == CardStatus.DONE

    output_path = workspace / "agent_output" / "runtime_truth.txt"
    assert output_path.read_text(encoding="utf-8") == "runtime-ok"

    assert fake_client.closed is True
    assert len(fake_client.requests) >= 2
    assert all(row["path"] == "/chat/completions" for row in fake_client.requests)
    assert {row["headers"].get("x-orket-session-id", "") for row in fake_client.requests} == {"runtime-session-1"}
    assert {row["headers"].get("x-client-session", "") for row in fake_client.requests} == {"runtime-session-1"}
    assert any("Task 1" in json.dumps(row["payload"].get("messages", [])) for row in fake_client.requests)

    receipt_rows: list[dict[str, Any]] = []
    for receipt_path in (workspace / "observability").rglob("protocol_receipts.log"):
        for line in receipt_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                receipt_rows.append(json.loads(line))
    assert any(row.get("tool") == "write_file" for row in receipt_rows)
    assert any(row.get("tool") == "read_file" for row in receipt_rows)
    assert any(row.get("tool") == "update_issue_status" for row in receipt_rows)

    raw_payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (workspace / "observability").rglob("model_response_raw.json")
    ]
    assert any(payload.get("provider") == "openai-compat" for payload in raw_payloads)
    assert any(payload.get("profile_id") and payload.get("profile_id") != "unresolved" for payload in raw_payloads)
    assert any(payload.get("task_class") == "strict_json" for payload in raw_payloads)
