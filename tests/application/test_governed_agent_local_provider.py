# Layer: contract
from __future__ import annotations

from dataclasses import replace

import pytest

from orket.adapters.llm import local_model_provider_runtime_target as targeting
from orket.adapters.llm.local_model_provider import ModelResponse
from orket.application.services.governed_agent_api_composition import _settings
from orket.application.services.governed_agent_broker_service import GovernedAgentResolvedModelProfile
from orket.application.services.governed_agent_model_provider import GovernedAgentLocalModelProvider
from orket.application.services.local_model_factory import create_local_model_provider
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget
from orket.exceptions import ModelConnectionError
from orket_extension_sdk import AgentModelCallRequest
from orket_extension_sdk.agent_fixtures import agent_model_call_request


def _target(provider="llama_cpp", status="OK") -> ProviderRuntimeTarget:
    return ProviderRuntimeTarget(provider, "openai_compat", "qwen", "qwen", "http://127.0.0.1:8080/v1",
                                 "requested", "http_models", ("qwen",), (), (), False, False, status)


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["llama_cpp", "lmstudio", "openai_compat"])
async def test_openai_transport_preserves_governed_usage_and_truncation(provider) -> None:
    """Layer: contract. OpenAI-format usage and finish reason become truthful host receipts."""
    class Client:
        provider_name = provider

        async def complete(self, messages, runtime_context):
            assert runtime_context["local_prompt_max_output_tokens"] == 128
            return ModelResponse('{"result": 1}', {"input_tokens": 25, "output_tokens": 128,
                "openai_compat": {"choices": [{"finish_reason": "length"}]}})

    profile = GovernedAgentResolvedModelProfile("local.planner", f"{provider}:qwen", provider, None, "qwen", None)
    request = agent_model_call_request()
    request["max_output_tokens"] = 128
    observation = await GovernedAgentLocalModelProvider({"qwen": Client()}).call(
        request=AgentModelCallRequest.from_wire(request), profile=profile)
    assert observation.response == {"result": 1}
    assert observation.usage_posture == "measured"
    assert observation.input_tokens == 25 and observation.output_tokens == 128
    assert observation.finish_reason == "length" and observation.truncated


@pytest.mark.asyncio
async def test_blocked_target_is_not_cached_or_admitted(monkeypatch) -> None:
    """Layer: contract. A nonempty but quarantined target cannot proceed on a retry."""
    provider = create_local_model_provider("qwen", provider="llama_cpp", base_url=_target().base_url,
                                  timeout=30, environment={})
    async def resolve(**kwargs):
        return _target(status="BLOCKED")
    monkeypatch.setattr(targeting, "resolve_provider_runtime_target", resolve)
    try:
        for _ in range(2):
            with pytest.raises(ModelConnectionError):
                await targeting.ensure_provider_runtime_target(provider)
            assert provider._runtime_target is None
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_pinned_target_prevents_environment_model_reselection(monkeypatch) -> None:
    """Layer: contract. An admitted exact target remains bound even with auto-selection enabled."""
    monkeypatch.setenv("ORKET_PROVIDER_RUNTIME_AUTO_SELECT_MODEL", "1")
    async def forbidden(**kwargs):
        pytest.fail("Pinned governed model must not be resolved a second time")
    monkeypatch.setattr(targeting, "resolve_provider_runtime_target", forbidden)
    provider = create_local_model_provider("qwen", provider="llama_cpp", base_url=_target().base_url,
                                  runtime_target=_target())
    try:
        assert await targeting.ensure_provider_runtime_target(provider) == "qwen"
    finally:
        await provider.close()


@pytest.mark.parametrize("target", [_target(status="BLOCKED"), replace(_target(), model_id="other"),
                                     replace(_target(), requested_provider="lmstudio")])
def test_pinned_target_rejects_mismatched_admission(target) -> None:
    """Layer: contract. Admission identity and client identity must agree before client creation."""
    with pytest.raises(ValueError, match="E_PROVIDER_PINNED_TARGET_MISMATCH"):
        create_local_model_provider("qwen", provider="llama_cpp", base_url=_target().base_url, runtime_target=target)


@pytest.mark.parametrize("provider", ["llama_cpp", "lmstudio", "ollama", "openai_compat"])
def test_api_settings_select_explicit_local_provider(monkeypatch, provider) -> None:
    """Layer: contract. Generic API configuration applies to all admitted provider tokens."""
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PROVIDER", provider)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_MODEL", "exact-model")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_BASE_URL", "http://127.0.0.1:8080/v1")
    settings = _settings()
    assert settings.provider_mode == provider and settings.default_model == "exact-model"
    assert settings.provider_base_url == "http://127.0.0.1:8080/v1"


def test_llama_cpp_does_not_inherit_ollama_model(monkeypatch) -> None:
    """Layer: contract. A provider change cannot silently consume another provider's model setting."""
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PROVIDER", "llama_cpp")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_SUPERVISOR_ENABLED", "1")
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL", "ollama-only-model")
    monkeypatch.delenv("ORKET_GOVERNED_AGENT_MODEL", raising=False)
    for role in ("PLANNER", "ACTOR", "CRITIC"):
        monkeypatch.delenv(f"ORKET_GOVERNED_AGENT_{role}_MODEL", raising=False)
    with pytest.raises(ValueError, match="E_AGENT_LOCAL_MODEL_REQUIRED"):
        _settings()


def test_api_defaults_to_llama_cpp_without_legacy_selection(monkeypatch) -> None:
    """Layer: contract. Generic model configuration prefers llama.cpp without an override."""
    monkeypatch.delenv("ORKET_GOVERNED_AGENT_PROVIDER", raising=False)
    monkeypatch.delenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL", raising=False)
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_MODEL", "qwen")
    assert _settings().provider_mode == "llama_cpp"


def test_text_observation_preserves_non_json_content() -> None:
    """Layer: contract. Admitted text responses are not converted into failed JSON calls."""
    from orket.application.services.governed_agent_model_provider import _observation
    response = _observation(ModelResponse("plain response", {}), response_mode="text")
    assert response.status == "returned" and response.response == "plain response"
    assert response.usage_posture == "unknown"
