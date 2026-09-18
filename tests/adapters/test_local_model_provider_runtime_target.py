"""Layer: contract. Explicit admission replaces client-type-dependent preparation."""
from dataclasses import FrozenInstanceError, replace

import pytest

from orket.adapters.llm.local_model_provider import LocalModelProvider
from orket.application.services.local_model_factory import create_local_model_provider
from orket.core.contracts.provider_preparation import ProviderPreparationRequest, require_prepared_target
from orket.core.contracts.provider_runtime import ProviderRuntimeTarget
from orket.exceptions import ModelConnectionError

pytestmark = pytest.mark.contract


def request():
    return ProviderPreparationRequest("openai_compat", "requested", "localhost:1234/v1/", 5, "fixture-secret")


def target():
    return ProviderRuntimeTarget("openai_compat", "openai_compat", "requested", "selected",
                                 "http://localhost:1234/v1", "auto_selected", "test", ("selected",),
                                 (), (), False, False, "OK")


def test_raw_adapter_requires_explicit_preparation_port():
    with pytest.raises(TypeError, match="runtime_preparation"):
        LocalModelProvider("fixture", prompt_policy=object())


def test_preparation_inputs_are_immutable_and_admitted_model_can_differ_from_request():
    captured = request()
    with pytest.raises(FrozenInstanceError):
        captured.requested_model = "mutated"
    assert "fixture-secret" not in repr(captured)
    assert captured.base_url == "http://localhost:1234/v1"
    require_prepared_target(captured, target())


@pytest.mark.parametrize("changes", [
    {"status": "BLOCKED"}, {"model_id": ""}, {"requested_provider": "lmstudio"},
    {"canonical_provider": "ollama"}, {"requested_model": "another-request"},
    {"base_url": "http://localhost:4567/v1"},
])
def test_preparation_rejects_unadmitted_or_mismatched_target(changes):
    with pytest.raises(ModelConnectionError):
        require_prepared_target(request(), replace(target(), **changes))


@pytest.mark.asyncio
async def test_ollama_client_default_endpoint_does_not_read_excluded_ambient_host(monkeypatch):
    monkeypatch.setenv("OLLAMA_HOST", "http://127.0.0.1:19991")
    provider = create_local_model_provider("fixture", provider="ollama", environment={})
    try:
        assert provider.ollama_host == "http://127.0.0.1:11434"
        assert str(provider.client._client.base_url).rstrip("/") == provider.ollama_host
    finally:
        await provider.close()
        assert provider.client._client.is_closed
