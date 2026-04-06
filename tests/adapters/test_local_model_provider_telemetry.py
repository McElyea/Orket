from __future__ import annotations

# Layer: contract
import json
from typing import Any

import httpx
import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider, ModelResponse
from orket.exceptions import ModelProviderError
from orket.runtime.provider_runtime_target import ProviderRuntimeTarget


class _FakeClient:
    async def chat(self, model, messages, options, format=None):  # type: ignore[no-untyped-def]
        return {
            "message": {"content": "ok"},
            "prompt_eval_count": 12,
            "eval_count": 8,
            "prompt_eval_duration": 120_000_000,
            "eval_duration": 320_000_000,
            "total_duration": 500_000_000,
        }


@pytest.mark.asyncio
async def test_local_model_provider_emits_usage_and_timings_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="dummy")
    provider.client = _FakeClient()

    response = await provider.complete([{"role": "user", "content": "hello"}])

    assert isinstance(response, ModelResponse)
    assert response.content == "ok"
    assert response.raw["usage"] == {
        "prompt_tokens": 12,
        "completion_tokens": 8,
        "total_tokens": 20,
    }
    assert response.raw["timings"] == {
        "prompt_ms": 120.0,
        "predicted_ms": 320.0,
        "total_ms": 500.0,
    }
    assert response.raw["ollama_request_format"] is None
    assert response.raw["ollama_format_fallback_used"] is False


def test_local_model_provider_ns_to_ms_is_type_strict() -> None:
    assert LocalModelProvider._ns_to_ms(1_000_000) == 1.0
    assert LocalModelProvider._ns_to_ms(2.5) == 2.5 / 1_000_000.0
    assert LocalModelProvider._ns_to_ms("bad") is None


@pytest.mark.parametrize(
    ("raw_provider", "expected_backend", "expected_name"),
    [
        ("ollama", "ollama", "ollama"),
        ("openai_compat", "openai_compat", "openai_compat"),
        ("lmstudio", "openai_compat", "lmstudio"),
        ("unknown-provider", "ollama", "ollama"),
    ],
)
def test_local_model_provider_maps_provider_env_consistently(
    monkeypatch: pytest.MonkeyPatch,
    raw_provider: str,
    expected_backend: str,
    expected_name: str,
) -> None:
    """Layer: unit. Verifies provider backend and provider name share one normalization source."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", raw_provider)
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)

    provider = LocalModelProvider(model="dummy")

    assert provider.provider_backend == expected_backend
    assert provider.provider_name == expected_name


def test_local_model_provider_explicit_provider_override_beats_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies per-instance provider overrides do not depend on global env."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:9999/v1")

    provider = LocalModelProvider(
        model="dummy",
        provider="lmstudio",
        base_url="http://127.0.0.1:1234/v1",
        api_key="test-key",
    )

    assert provider.provider_backend == "openai_compat"
    assert provider.provider_name == "lmstudio"
    assert provider.openai_base_url == "http://127.0.0.1:1234/v1"
    assert provider.openai_api_key == "test-key"


def test_local_model_provider_separates_connect_and_read_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: unit. Verifies openai-compatible clients fail fast on connect while preserving a longer stream read budget."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "openai_compat")

    provider = LocalModelProvider(
        model="dummy",
        timeout=300,
        connect_timeout_seconds=15.0,
    )

    assert isinstance(provider.client, httpx.AsyncClient)
    timeout = provider.client.timeout
    assert timeout.connect == 15.0
    assert timeout.read == 300.0
    assert timeout.write == 30.0
    assert timeout.pool == 10.0


@pytest.mark.asyncio
async def test_local_model_provider_lmstudio_openai_compat_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _fake_resolve(**kwargs: Any) -> ProviderRuntimeTarget:
        _ = kwargs
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="dummy",
            model_id="dummy",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="requested",
            inventory_source="test",
            available_models=("dummy",),
            loaded_models_before=("dummy",),
            loaded_models_after=("dummy",),
            auto_load_attempted=False,
            auto_load_performed=False,
            status="OK",
        )

    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider_runtime_target.resolve_provider_runtime_target",
        _fake_resolve,
    )

    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "dummy"
        assert isinstance(payload["messages"], list)
        assert request.headers["x-orket-request-id"].startswith("orket-")
        assert bool(request.headers["x-orket-session-id"])
        assert request.headers["x-client-session"] == request.headers["x-orket-session-id"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "hello"}])
    await provider.close()

    assert isinstance(response, ModelResponse)
    assert response.content == "ok"
    assert response.raw["provider"] == "openai-compat"
    assert response.raw["provider_backend"] == "openai_compat"
    assert response.raw["provider_name"] == "lmstudio"
    assert response.raw["orket_request_id"].startswith("orket-")
    assert bool(response.raw["orket_session_id"])
    assert bool(response.raw["prompt_fingerprint"])
    assert response.raw["http"]["status_code"] == 200
    assert "content-type" in response.raw["http"]["response_headers"]
    assert response.raw["usage"] == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
        "total_tokens": 10,
    }
    assert isinstance(response.raw["timings"]["prompt_ms"], float)
    assert isinstance(response.raw["timings"]["predicted_ms"], float)


@pytest.mark.asyncio
async def test_local_model_provider_collapses_adjacent_user_blocks_for_gemma_requests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies Gemma LM Studio requests compact verbose governed packets before submission."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="google/gemma-4-26b-a4b")

    async def _fake_resolve(**kwargs: Any) -> ProviderRuntimeTarget:
        _ = kwargs
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="google/gemma-4-26b-a4b",
            model_id="google/gemma-4-26b-a4b",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="requested",
            inventory_source="test",
            available_models=("google/gemma-4-26b-a4b",),
            loaded_models_before=("google/gemma-4-26b-a4b",),
            loaded_models_after=("google/gemma-4-26b-a4b",),
            auto_load_attempted=False,
            auto_load_performed=False,
            status="OK",
        )

    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider_runtime_target.resolve_provider_runtime_target",
        _fake_resolve,
    )

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert [message["role"] for message in payload["messages"]] == ["system", "user"]
        assert "MODE: compact governed tool turn" in payload["messages"][0]["content"]
        assert "ALLOWED TOOLS:" not in payload["messages"][0]["content"]
        assert "TURN PACKET:" in payload["messages"][1]["content"]
        assert "Issue CWR-01" in payload["messages"][1]["content"]
        assert "Execution Context JSON:\n{}" not in payload["messages"][1]["content"]
        assert "Guard Decision Contract:" not in payload["messages"][1]["content"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-gemma-shape",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 2, "total_tokens": 11},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [
            {"role": "system", "content": "IDENTITY: integrity_guard"},
            {"role": "user", "content": "Issue CWR-01"},
            {"role": "user", "content": "Execution Context JSON:\n{}"},
            {"role": "user", "content": "Guard Decision Contract:\n- Do not emit blocked for this turn."},
        ],
        runtime_context={"local_prompt_task_class": "tool_call"},
    )
    await provider.close()

    assert response.raw["openai_request_message_count"] == 2
    assert response.raw["openai_request_role_sequence"] == ["system", "user"]
    assert response.raw["openai_request_role_counts"] == {"system": 1, "user": 1}
    assert "message_packet_compacted:gemma_tool_turn_v1:4->2" in response.raw["local_prompting_warnings"]


@pytest.mark.asyncio
async def test_local_model_provider_honors_bench_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setenv("ORKET_BENCH_TEMPERATURE", "0")
    monkeypatch.setenv("ORKET_BENCH_SEED", "1337")
    monkeypatch.setenv("ORKET_LLM_OPENAI_RESPONSE_FORMAT", "text")
    provider = LocalModelProvider(model="dummy", temperature=0.7, seed=None)

    async def _fake_resolve(**kwargs: Any) -> ProviderRuntimeTarget:
        _ = kwargs
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="dummy",
            model_id="dummy",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="requested",
            inventory_source="test",
            available_models=("dummy",),
            loaded_models_before=("dummy",),
            loaded_models_after=("dummy",),
            auto_load_attempted=False,
            auto_load_performed=False,
            status="OK",
        )

    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider_runtime_target.resolve_provider_runtime_target",
        _fake_resolve,
    )

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["temperature"] == 0.0
        assert payload["seed"] == 1337
        assert payload["response_format"] == {"type": "text"}
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "hello"}])
    await provider.close()
    assert isinstance(response, ModelResponse)


@pytest.mark.asyncio
async def test_local_model_provider_rejects_non_openai_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")
    called = False

    async def _handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 1, "total_tokens": 3},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    with pytest.raises(ModelProviderError, match="OpenAI-compatible messages require roles"):
        await provider.complete(
            [
                {"role": "coder", "content": "prior output"},
                {"role": "developer", "content": "system hint"},
            ]
        )
    await provider.close()
    assert called is False


@pytest.mark.asyncio
async def test_local_model_provider_uses_runtime_context_for_orket_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-orket-session-id"] == "seat-42"
        assert request.headers["x-client-session"] == "seat-42"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-ctx",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "hello"}],
        runtime_context={"seat_id": "seat-42"},
    )
    await provider.close()
    assert response.raw["orket_session_id"] == "seat-42"
    assert response.raw["orket_session_epoch"] == 0


@pytest.mark.asyncio
async def test_local_model_provider_captures_openai_tool_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")

    async def _handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-tool",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"},
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete([{"role": "user", "content": "tool"}])
    await provider.close()
    assert response.raw["tool_calls"][0]["id"] == "call_1"


@pytest.mark.asyncio
async def test_local_model_provider_applies_local_prompt_profile_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="qwen3.5-4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["max_tokens"] == 512
        assert payload["top_p"] == 1.0
        assert payload["temperature"] == 0.0
        assert payload["stop"] == ["<|json_end|>", "</s>"]
        assert payload["seed"] == 41
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-1",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "hello"}],
        runtime_context={"protocol_governed_enabled": True, "local_prompt_task_class": "strict_json"},
    )
    await provider.close()
    assert response.raw["profile_id"] == "openai_compat.qwen.openai_messages.v1"
    assert response.raw["task_class"] == "strict_json"
    assert response.raw["template_hash_alg"] == "sha256"


@pytest.mark.asyncio
async def test_local_model_provider_uses_native_write_tool_for_gemma_write_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="google/gemma-4-26b-a4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["tool_choice"] == "required"
        assert payload["reasoning_effort"] == "none"
        assert len(payload["tools"]) == 1
        tool = payload["tools"][0]["function"]
        assert tool["name"] == "write_file"
        assert tool["parameters"]["properties"]["path"]["enum"] == ["agent_output/requirements.txt"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-native-tool",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": (
                                            '{"path":"agent_output/requirements.txt","content":"workflow_id"}'
                                        ),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "write the required file"}],
        runtime_context={
            "required_action_tools": ["write_file", "update_issue_status"],
            "required_write_paths": ["agent_output/requirements.txt"],
        },
    )
    await provider.close()

    assert response.raw["openai_native_tool_names"] == ["write_file"]
    assert response.raw["openai_tool_choice"] == "required"
    assert response.raw["openai_native_payload_overrides"] == {"reasoning_effort": "none"}


@pytest.mark.asyncio
async def test_local_model_provider_uses_native_read_tool_for_gemma_guard_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies Gemma guard turns expose only the bounded native read tool."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="google/gemma-4-26b-a4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["tool_choice"] == "required"
        assert payload["reasoning_effort"] == "none"
        assert len(payload["tools"]) == 1
        tool = payload["tools"][0]["function"]
        assert tool["name"] == "read_file"
        assert tool["parameters"]["properties"]["path"]["enum"] == ["agent_output/requirements.txt"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-native-read",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"agent_output/requirements.txt"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "read the required file"}],
        runtime_context={
            "required_action_tools": ["read_file", "update_issue_status"],
            "required_read_paths": ["agent_output/requirements.txt"],
            "required_statuses": ["done"],
        },
    )
    await provider.close()

    assert response.raw["openai_native_tool_names"] == ["read_file"]
    assert response.raw["openai_tool_choice"] == "required"
    assert response.raw["openai_native_payload_overrides"] == {"reasoning_effort": "none"}


@pytest.mark.asyncio
async def test_local_model_provider_uses_native_read_and_write_tools_for_gemma_mixed_turns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies mixed Gemma turns expose only the admitted native read/write tools."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="google/gemma-4-26b-a4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["tool_choice"] == "required"
        assert payload["reasoning_effort"] == "none"
        assert [tool["function"]["name"] for tool in payload["tools"]] == ["read_file", "write_file"]
        assert payload["tools"][0]["function"]["parameters"]["properties"]["path"]["enum"] == [
            "agent_output/requirements.txt"
        ]
        assert payload["tools"][1]["function"]["parameters"]["properties"]["path"]["enum"] == [
            "agent_output/design.txt"
        ]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-native-mixed",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"agent_output/requirements.txt"}',
                                    },
                                },
                                {
                                    "id": "call_2",
                                    "type": "function",
                                    "function": {
                                        "name": "write_file",
                                        "arguments": (
                                            '{"path":"agent_output/design.txt","content":"{\\"modules\\": []}"}'
                                        ),
                                    },
                                },
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "read then write"}],
        runtime_context={
            "required_action_tools": ["read_file", "write_file", "update_issue_status"],
            "required_read_paths": ["agent_output/requirements.txt"],
            "required_write_paths": ["agent_output/design.txt"],
            "required_statuses": ["code_review"],
        },
    )
    await provider.close()

    assert response.raw["openai_native_tool_names"] == ["read_file", "write_file"]
    assert response.raw["openai_tool_choice"] == "required"
    assert response.raw["openai_native_payload_overrides"] == {"reasoning_effort": "none"}


@pytest.mark.asyncio
async def test_local_model_provider_uses_native_read_tool_for_gemma_guard_turns_from_scope_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies Gemma guard turns recover bounded read paths from scope fallback surfaces."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="google/gemma-4-26b-a4b")

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["tool_choice"] == "required"
        assert payload["reasoning_effort"] == "none"
        assert [tool["function"]["name"] for tool in payload["tools"]] == ["read_file"]
        assert payload["tools"][0]["function"]["parameters"]["properties"]["path"]["enum"] == [
            "agent_output/requirements.txt"
        ]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-native-guard-fallback",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": '{"path":"agent_output/requirements.txt"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "verify the required file"}],
        runtime_context={
            "required_statuses": ["done"],
            "artifact_contract": {
                "review_read_paths": ["agent_output/requirements.txt"],
            },
            "verification_scope": {
                "declared_interfaces": ["read_file", "update_issue_status"],
                "active_context": ["agent_output/requirements.txt"],
            },
        },
    )
    await provider.close()

    assert response.raw["openai_native_tool_names"] == ["read_file"]
    assert response.raw["openai_tool_choice"] == "required"
    assert response.raw["openai_native_payload_overrides"] == {"reasoning_effort": "none"}


@pytest.mark.asyncio
async def test_local_model_provider_uses_explicit_native_tool_contract_for_openai_compat(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies explicit native tool contracts can drive FunctionGemma-style OpenAI-compatible turns."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="functiongemma-270m-it")

    async def _fake_resolve(**kwargs: Any) -> ProviderRuntimeTarget:
        _ = kwargs
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="functiongemma-270m-it",
            model_id="functiongemma-270m-it",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="requested_loaded",
            inventory_source="test",
            available_models=("functiongemma-270m-it",),
            loaded_models_before=("functiongemma-270m-it",),
            loaded_models_after=("functiongemma-270m-it",),
            auto_load_attempted=False,
            auto_load_performed=False,
            status="OK",
        )

    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider_runtime_target.resolve_provider_runtime_target",
        _fake_resolve,
    )

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["tool_choice"] == "required"
        assert payload["reasoning_effort"] == "none"
        assert [tool["function"]["name"] for tool in payload["tools"]] == ["emit_judgment"]
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-functiongemma-tool",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "emit_judgment",
                                        "arguments": '{"verdict":"pass","tool_selection":"pass","argument_presence":"pass","argument_shape":"pass","extra_undeclared_tool_calls":"pass","malformed_output_shape":"pass","rationale":"ok"}',
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 7, "completion_tokens": 3, "total_tokens": 10},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    response = await provider.complete(
        [{"role": "user", "content": "Judge this turn"}],
        runtime_context={
            "local_prompt_task_class": "strict_json",
            "native_tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "emit_judgment",
                        "description": "Emit one advisory judgment.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
            ],
            "native_tool_choice": "required",
            "native_payload_overrides": {"reasoning_effort": "none"},
        },
    )
    await provider.close()

    assert response.raw["openai_native_tool_names"] == ["emit_judgment"]
    assert response.raw["openai_tool_choice"] == "required"
    assert response.raw["tool_calls"][0]["function"]["name"] == "emit_judgment"


@pytest.mark.asyncio
async def test_local_model_provider_ollama_strict_tasks_request_json_format(monkeypatch: pytest.MonkeyPatch) -> None:
    """Layer: contract. Verifies Ollama strict_json turns request provider JSON mode."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="qwen2.5-coder:7b")
    seen: dict[str, Any] = {}

    class _CaptureClient:
        async def chat(self, model, messages, options, format=None):  # type: ignore[no-untyped-def]
            seen["format"] = format
            return {
                "message": {"content": '{"ok":true,"case_id":"strict-json-0000-732"}'},
                "prompt_eval_count": 4,
                "eval_count": 2,
                "prompt_eval_duration": 100_000_000,
                "eval_duration": 90_000_000,
                "total_duration": 210_000_000,
            }

    provider.client = _CaptureClient()
    response = await provider.complete(
        [{"role": "user", "content": "Return strict JSON"}],
        runtime_context={"protocol_governed_enabled": True, "local_prompt_task_class": "strict_json"},
    )
    assert seen["format"] == "json"
    assert response.raw["ollama_request_format"] == "json"
    assert response.raw["ollama_format_fallback_used"] is False


@pytest.mark.asyncio
async def test_local_model_provider_ollama_tool_call_turns_request_json_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies tool_call turns request provider JSON mode for the single-envelope contract."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="qwen2.5-coder:7b")
    seen: dict[str, Any] = {}

    class _CaptureClient:
        async def chat(self, model, messages, options, format=None):  # type: ignore[no-untyped-def]
            seen["format"] = format
            return {
                "message": {
                    "content": (
                        '{"content":"","tool_calls":['
                        '{"tool":"read_file","args":{"path":"agent_output/requirements.txt"}},'
                        '{"tool":"update_issue_status","args":{"status":"code_review"}}'
                        ']}'
                    )
                },
                "prompt_eval_count": 4,
                "eval_count": 2,
                "prompt_eval_duration": 100_000_000,
                "eval_duration": 90_000_000,
                "total_duration": 210_000_000,
            }

    provider.client = _CaptureClient()
    response = await provider.complete(
        [{"role": "user", "content": "Return required tool calls"}],
        runtime_context={"required_action_tools": ["read_file", "update_issue_status"]},
    )
    assert seen["format"] == "json"
    assert response.raw["ollama_request_format"] == "json"
    assert response.raw["task_class"] == "tool_call"


@pytest.mark.asyncio
async def test_local_model_provider_ollama_uses_explicit_native_tools_without_forcing_json_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Layer: contract. Verifies explicit native tools bypass Ollama format=json and capture provider tool calls."""
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="qwen2.5-coder:7b")
    seen: dict[str, Any] = {}

    class _CaptureClient:
        async def chat(self, model, messages, options, format=None, tools=None):  # type: ignore[no-untyped-def]
            seen["format"] = format
            seen["tools"] = tools
            return {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "type": "function",
                            "function": {
                                "name": "emit_judgment",
                                "arguments": {
                                    "verdict": "pass",
                                    "tool_selection": "pass",
                                    "argument_presence": "pass",
                                    "argument_shape": "pass",
                                    "extra_undeclared_tool_calls": "pass",
                                    "malformed_output_shape": "pass",
                                    "rationale": "ok",
                                },
                            },
                        }
                    ],
                },
                "prompt_eval_count": 4,
                "eval_count": 2,
                "prompt_eval_duration": 100_000_000,
                "eval_duration": 90_000_000,
                "total_duration": 210_000_000,
            }

    provider.client = _CaptureClient()
    response = await provider.complete(
        [{"role": "user", "content": "Judge this turn"}],
        runtime_context={
            "local_prompt_task_class": "strict_json",
            "native_tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "emit_judgment",
                        "description": "Emit one advisory judgment.",
                        "parameters": {"type": "object", "properties": {}, "required": []},
                    },
                }
            ],
            "native_tool_choice": "required",
        },
    )

    assert seen["format"] is None
    assert [tool["function"]["name"] for tool in seen["tools"]] == ["emit_judgment"]
    assert response.raw["ollama_request_format"] is None
    assert response.raw["ollama_native_tool_names"] == ["emit_judgment"]
    assert response.raw["tool_calls"][0]["function"]["name"] == "emit_judgment"


@pytest.mark.asyncio
async def test_local_model_provider_clear_context_rotates_openai_session_id(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    provider = LocalModelProvider(model="dummy")
    seen_session_ids: list[str] = []

    async def _handler(request: httpx.Request) -> httpx.Response:
        seen_session_ids.append(request.headers["x-orket-session-id"])
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-ctx",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    provider.client = httpx.AsyncClient(
        base_url="http://127.0.0.1:1234/v1",
        transport=httpx.MockTransport(_handler),
    )
    first = await provider.complete([{"role": "user", "content": "hello"}], runtime_context={"seat_id": "seat-42"})
    await provider.clear_context()
    second = await provider.complete([{"role": "user", "content": "hello"}], runtime_context={"seat_id": "seat-42"})
    await provider.close()

    assert seen_session_ids == ["seat-42", "seat-42-ctx1"]
    assert first.raw["orket_session_epoch"] == 0
    assert second.raw["orket_session_epoch"] == 1


@pytest.mark.asyncio
async def test_local_model_provider_uses_shared_runtime_target_before_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    seen: dict[str, Any] = {}

    async def _fake_resolve(**kwargs: Any) -> ProviderRuntimeTarget:
        seen.update(kwargs)
        return ProviderRuntimeTarget(
            requested_provider="lmstudio",
            canonical_provider="openai_compat",
            requested_model="qwen3.5-coder",
            model_id="qwen3.5-4b",
            base_url="http://127.0.0.1:1234/v1",
            resolution_mode="auto_selected_from_disk",
            inventory_source="lms_cli",
            available_models=("qwen3.5-0.8b", "qwen3.5-4b"),
            loaded_models_before=(),
            loaded_models_after=("qwen3.5-4b",),
            auto_load_attempted=True,
            auto_load_performed=True,
            status="OK",
        )

    async def _handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        assert payload["model"] == "qwen3.5-4b"
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-target",
                "choices": [{"message": {"role": "assistant", "content": "ok"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5},
            },
        )

    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider_runtime_target.resolve_provider_runtime_target",
        _fake_resolve,
    )
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider.httpx.AsyncClient",
        lambda *args, **kwargs: real_async_client(
            base_url="http://127.0.0.1:1234/v1",
            transport=httpx.MockTransport(_handler),
        ),
    )
    provider = LocalModelProvider(model="qwen3.5-coder")

    response = await provider.complete([{"role": "user", "content": "hello"}])
    await provider.close()

    assert seen["provider"] == "lmstudio"
    assert response.raw["requested_model"] == "qwen3.5-coder"
    assert response.raw["model"] == "qwen3.5-4b"
    assert response.raw["runtime_target"]["resolution_mode"] == "auto_selected_from_disk"


@pytest.mark.asyncio
async def test_local_model_provider_ollama_strict_format_failure_is_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "ollama")
    monkeypatch.delenv("ORKET_MODEL_PROVIDER", raising=False)
    provider = LocalModelProvider(model="qwen2.5-coder:7b")

    class _NoFormatClient:
        async def chat(self, model, messages, options):  # type: ignore[no-untyped-def]
            _ = (model, messages, options)
            return {"message": {"content": "ok"}}

    provider.client = _NoFormatClient()

    with pytest.raises(ModelProviderError, match="does not support format='json'"):
        await provider.complete(
            [{"role": "user", "content": "Return strict JSON"}],
            runtime_context={"protocol_governed_enabled": True, "local_prompt_task_class": "strict_json"},
        )


@pytest.mark.asyncio
async def test_local_model_provider_close_is_idempotent_for_openai_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeClient:
        def __init__(self):
            self.close_calls = 0

        async def aclose(self) -> None:
            self.close_calls += 1

    fake_client = _FakeClient()
    monkeypatch.setenv("ORKET_LLM_PROVIDER", "openai_compat")
    monkeypatch.setattr(
        "orket.adapters.llm.local_model_provider.httpx.AsyncClient",
        lambda *args, **kwargs: fake_client,
    )

    provider = LocalModelProvider(model="qwen3.5-4b")
    await provider.close()
    await provider.close()
    assert fake_client.close_calls == 1
