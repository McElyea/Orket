from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from orket.adapters.llm import local_model_provider as local_model_provider_module
from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.workflows.turn_executor import TurnExecutor
from orket.application.workflows.turn_executor_runtime import invoke_model_complete
from orket.core.domain.state_machine import StateMachine
from orket.core.policies.tool_gate import ToolGate
from orket.schema import IssueConfig, RoleConfig


class _FakeOpenAIClient:
    def __init__(self) -> None:
        self.post_calls = 0

    async def post(self, path: str, headers: dict[str, str], **kwargs: Any) -> httpx.Response:
        _ = headers
        _ = kwargs.get("json")
        self.post_calls += 1
        envelope = {
            "content": "",
            "tool_calls": [{"tool": "write_file", "args": {"path": "agent_output/main.py", "content": "print(1)"}}],
        }
        request = httpx.Request("POST", f"http://127.0.0.1:1234/v1{path}")
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-bridge",
                "choices": [{"message": {"role": "assistant", "content": json.dumps(envelope)}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2, "total_tokens": 6},
            },
            headers={"content-type": "application/json"},
            request=request,
        )

    async def aclose(self) -> None:
        return None


class _WrappedClient:
    def __init__(self, provider: LocalModelProvider) -> None:
        self.provider = provider

    async def complete(self, messages: list[dict[str, str]]) -> Any:
        return await self.provider.complete(messages)


class _Toolbox:
    async def execute(self, tool_name: str, args: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
        _ = (tool_name, args, context)
        return {"ok": True}


@pytest.mark.asyncio
async def test_invoke_model_complete_passes_runtime_context_to_direct_complete() -> None:
    """Layer: contract. Verifies direct model-client complete() receives runtime_context on success."""

    class _DirectClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def complete(
            self,
            messages: list[dict[str, str]],
            runtime_context: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls.append({"messages": messages, "runtime_context": runtime_context})
            return {"content": "ok"}

    client = _DirectClient()
    messages = [{"role": "user", "content": "bridge"}]
    context = {"session_id": "run-ctx-direct", "turn_index": 3}

    result = await invoke_model_complete(client, messages, context)

    assert result == {"content": "ok"}
    assert client.calls == [{"messages": messages, "runtime_context": context}]


@pytest.mark.asyncio
async def test_invoke_model_complete_uses_provider_fallback_when_wrapper_omits_runtime_context() -> None:
    """Layer: contract. Verifies wrapped clients fall back to provider.complete(..., runtime_context=...)."""

    class _Provider:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def complete(
            self,
            messages: list[dict[str, str]],
            runtime_context: dict[str, Any] | None = None,
        ) -> dict[str, Any]:
            self.calls.append({"messages": messages, "runtime_context": runtime_context})
            return {"content": "provider-ok"}

    class _WrappedClient:
        def __init__(self, provider: _Provider) -> None:
            self.provider = provider
            self.wrapper_calls = 0

        async def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
            self.wrapper_calls += 1
            return {"content": "wrapper-ok"}

    provider = _Provider()
    client = _WrappedClient(provider)
    messages = [{"role": "user", "content": "bridge"}]
    context = {"session_id": "run-ctx-provider", "turn_index": 4}

    result = await invoke_model_complete(client, messages, context)

    assert result == {"content": "provider-ok"}
    assert client.wrapper_calls == 0
    assert provider.calls == [{"messages": messages, "runtime_context": context}]


@pytest.mark.asyncio
async def test_turn_executor_bridges_runtime_context_through_wrapped_model_client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_client = _FakeOpenAIClient()
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.delenv("ORKET_LOCAL_PROMPTING_MODE", raising=False)
    monkeypatch.setattr(local_model_provider_module.httpx, "AsyncClient", lambda *args, **kwargs: fake_client)

    provider = LocalModelProvider(model="unknown-unmapped-model")
    model_client = _WrappedClient(provider)
    executor = TurnExecutor(
        state_machine=StateMachine(),
        tool_gate=ToolGate(organization=None, workspace_root=tmp_path),
        workspace=tmp_path,
    )
    issue = IssueConfig(id="ISSUE-1", summary="Bridge runtime context", seat="developer")
    role = RoleConfig(id="DEV", summary="developer", description="Build", tools=["write_file"])
    context = {
        "session_id": "run-ctx-1",
        "issue_id": "ISSUE-1",
        "role": "developer",
        "roles": ["developer"],
        "current_status": "ready",
        "selected_model": "unknown-unmapped-model",
        "turn_index": 1,
        "history": [],
        "protocol_governed_enabled": True,
        "local_prompting_mode": "enforce",
        "required_action_tools": ["write_file"],
        "required_statuses": [],
    }

    result = await executor.execute_turn(
        issue=issue,
        role=role,
        model_client=model_client,
        toolbox=_Toolbox(),
        context=context,
        system_prompt="SYSTEM",
    )
    await provider.close()

    assert result.success is False
    assert "E_LOCAL_PROMPT_PROFILE_REQUIRED" in str(result.error or "")
    assert fake_client.post_calls == 0
