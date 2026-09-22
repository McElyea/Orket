"""Layer: contract. Provider omission and invalid input cannot select Ollama."""
from __future__ import annotations

import os

import pytest

from orket.application.services.governed_agent_api_composition import _configured_model
from orket.application.services.local_model_factory import (
    create_local_model_provider,
    create_local_model_provider_async,
)
from orket.application.services.model_selection_service import ModelSelectionService
from orket.core.contracts.provider_runtime import DEFAULT_LOCAL_MODEL, normalize_provider
from orket.exceptions import ModelConnectionError
from orket.runtime.config.defaults import configured_provider
from orket.runtime.config.local_prompt_profiles import normalize_provider_for_local_prompt_profile
from orket.runtime.config.provider_runtime_target import default_base_url
from orket.workloads.model_stream_v1 import _real_provider_name
from scripts.streaming.provider_identity import provider_identity

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def clean_provider_settings(monkeypatch):
    for key in ("ORKET_LLM_PROVIDER", "ORKET_MODEL_PROVIDER", "ORKET_MODEL_STREAM_REAL_PROVIDER",
                "ORKET_GOVERNED_AGENT_PROVIDER", "ORKET_GOVERNED_AGENT_MODEL",
                "ORKET_LLM_LLAMA_CPP_BASE_URL", "ORKET_LLAMA_CPP_BASE_URL"):
        monkeypatch.delenv(key, raising=False)


@pytest.mark.asyncio
async def test_omitted_provider_uses_llama_cpp_transport_and_endpoint(monkeypatch):
    monkeypatch.setattr("ollama.AsyncClient", lambda **kw: pytest.fail("Implicit Ollama client"))
    provider = (await create_local_model_provider_async(model=DEFAULT_LOCAL_MODEL))
    try:
        assert provider.provider_name == "llama_cpp"
        assert provider.provider_backend == "openai_compat"
        assert provider.openai_base_url == "http://127.0.0.1:8080/v1"
        assert default_base_url("") == provider.openai_base_url
    finally:
        await provider.close()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_unavailable_default_endpoint_does_not_switch_provider(monkeypatch):
    """Layer: integration. Real refused HTTP connection remains a llama.cpp failure."""
    monkeypatch.setattr("ollama.AsyncClient", lambda **kw: pytest.fail("Unexpected Ollama fallback"))
    provider = (await create_local_model_provider_async(model=DEFAULT_LOCAL_MODEL, base_url="http://127.0.0.1:1/v1"))
    try:
        with pytest.raises(ModelConnectionError, match="provider=llama_cpp"):
            await provider.complete([{"role": "user", "content": "OK"}])
        assert provider.provider_name == "llama_cpp"
    finally:
        await provider.close()


@pytest.mark.asyncio
# Layer: contract
async def test_defaults_and_blank_settings_preserve_provider_identity(monkeypatch):
    monkeypatch.setenv("ORKET_LLM_PROVIDER", " ")
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    assert configured_provider() == _real_provider_name() == "llama_cpp"
    assert provider_identity()["provider"] == "llama_cpp"
    assert normalize_provider("") == "openai_compat"
    assert normalize_provider_for_local_prompt_profile("") == "llama_cpp"
    selection = await ModelSelectionService(environment={}).prepare(preferences={}, user_settings={})
    assert selection.select("coder").final_model == DEFAULT_LOCAL_MODEL


def test_unknown_provider_is_rejected_before_client_creation(monkeypatch):
    monkeypatch.setattr("ollama.AsyncClient", lambda **kw: pytest.fail("Implicit Ollama client"))
    with pytest.raises(ValueError, match="E_UNKNOWN_PROVIDER_INPUT"):
        create_local_model_provider(model=DEFAULT_LOCAL_MODEL, provider="unknown-provider")


def test_legacy_model_variable_requires_explicit_ollama_provider(monkeypatch):
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_OLLAMA_MODEL", "legacy-ollama-model")
    assert configured_provider("ORKET_GOVERNED_AGENT_PROVIDER") == "llama_cpp"
    assert _configured_model(dict(os.environ)) == ""
    monkeypatch.setenv("ORKET_GOVERNED_AGENT_PROVIDER", "ollama")
    assert _configured_model(dict(os.environ)) == "legacy-ollama-model"


@pytest.mark.parametrize("provider", ["llama_cpp", "lmstudio", "ollama", "openai_compat"])
def test_explicit_provider_remains_authoritative(monkeypatch, provider):
    monkeypatch.setenv("ORKET_MODEL_PROVIDER", provider)
    assert configured_provider() == _real_provider_name() == provider
