"""Transport contracts for SDK options and unresolved local prompt profiles."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from orket.application.services import sdk_llm_provider
from orket.application.services.local_prompting_service import resolve_local_prompting_policy
from orket.application.services.sdk_llm_provider import LocalModelCapabilityProvider
from orket.capabilities.sync_bridge import run_coro_sync
from orket.runtime.config.local_prompt_profiles import DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH
from orket_extension_sdk.llm import GenerateRequest
from tests.helpers.provider_preparation import create_test_model_provider


class OllamaTransport:
    def __init__(self, observed):
        self.observed = observed

    async def chat(self, **kwargs):
        self.observed.append(kwargs["options"])
        return {"message": {"content": "controlled"}, "prompt_eval_count": 2, "eval_count": 1}

    async def aclose(self):
        return None


@pytest.mark.parametrize("backend", ["lmstudio", "ollama"])
@pytest.mark.parametrize("model", ["qwen2.5:7b", "unknown-model-family"])
# Layer: contract
def test_sdk_options_reach_transport_without_mutating_provider_defaults(monkeypatch, backend, model):
    observed = []

    def respond(request):
        observed.append(json.loads(request.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "controlled"}}]})

    monkeypatch.setenv("ORKET_LOCAL_PROMPTING_MODE", "shadow")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://controlled.test/v1")
    monkeypatch.setattr(sdk_llm_provider, "create_local_model_provider", create_test_model_provider)
    if backend == "ollama":
        monkeypatch.setattr("orket.adapters.llm.local_model_provider.ollama.AsyncClient", lambda **_: OllamaTransport(observed))
    provider = LocalModelCapabilityProvider(model=model, temperature=0.9, seed=None, provider=backend)
    if backend == "lmstudio":
        run_coro_sync(provider._provider.client.aclose())
        provider._provider.client = httpx.AsyncClient(base_url="http://controlled.test/v1", transport=httpx.MockTransport(respond))
    try:
        for temperature in (0.0, 0.65):
            provider.generate(GenerateRequest(system_prompt="", user_message="hello", max_tokens=512,
                                             temperature=temperature, stop_sequences=["  END\n", " ", "  END\n"]))
        for payload, temperature in zip(observed, (0.0, 0.65), strict=True):
            assert payload["max_tokens" if backend == "lmstudio" else "num_predict"] == 512
            assert payload["temperature"] == temperature
            assert payload["stop"][:2] == ["  END\n", " "]
            assert payload["stop"].count("  END\n") == 1
        assert provider._provider.temperature == 0.9
    finally:
        provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ollama", "openai_compat"])
# Layer: contract
async def test_unresolved_profile_preserves_only_explicit_generation_options(provider):
    result = await resolve_local_prompting_policy(provider_backend=provider, model="unknown-model-family",
        messages=[{"role": "user", "content": "hello"}], runtime_context={"local_prompting_mode": "shadow",
            "local_prompt_max_output_tokens": 37, "local_prompt_stop_sequences": [" END\n", " "]})
    payload = result.ollama_options_overrides() if provider == "ollama" else result.openai_payload_overrides()
    assert payload == {"num_predict" if provider == "ollama" else "max_tokens": 37, "stop": [" END\n", " "]}
    assert result.profile_id == "unresolved" and result.sampling_bundle == {"max_output_tokens": 37}


@pytest.mark.asyncio
@pytest.mark.parametrize("model", ["qwen2.5:7b", "unknown-model-family"])
@pytest.mark.parametrize(("key", "value"), [
    ("local_prompt_max_output_tokens", True), ("local_prompt_max_output_tokens", 1.5),
    ("local_prompt_max_output_tokens", 0), ("local_prompt_max_output_tokens", "12"),
    ("local_prompt_temperature", True), ("local_prompt_temperature", float("nan")),
    ("local_prompt_temperature", float("inf")), ("local_prompt_temperature", -0.1),
    ("local_prompt_stop_sequences", [""]), ("local_prompt_stop_sequences", [1]),
])
# Layer: contract
async def test_invalid_generation_options_are_rejected_for_every_profile(model, key, value):
    with pytest.raises(ValueError, match=key):
        await resolve_local_prompting_policy(provider_backend="ollama", model=model,
            messages=[{"role": "user", "content": "hello"}], runtime_context={"local_prompting_mode": "shadow", key: value})


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["ollama", "openai_compat"])
@pytest.mark.parametrize("mode", ["shadow", "compat", "enforce"])
# Layer: contract
async def test_large_request_never_widens_selected_profile(provider, mode):
    arguments = {"provider_backend": provider, "model": "qwen2.5:7b", "messages": [{"role": "user", "content": "hello"}]}
    baseline = await resolve_local_prompting_policy(**arguments, runtime_context={"local_prompting_mode": mode})
    result = await resolve_local_prompting_policy(**arguments, runtime_context={"local_prompting_mode": mode,
        "local_prompt_max_output_tokens": 999999, "local_prompt_stop_sequences": [" caller-stop\n"]})
    assert result.sampling_bundle["max_output_tokens"] == baseline.sampling_bundle["max_output_tokens"]
    assert result.effective_stop_sequences == (" caller-stop\n", *baseline.effective_stop_sequences)


@pytest.mark.asyncio
@pytest.mark.parametrize("stops", [["  PROFILE\n", " "], [""], [1]])
# Layer: integration
async def test_profile_file_preserves_exact_stops_or_rejects_invalid_elements(tmp_path, stops):
    payload = json.loads(await asyncio.to_thread(DEFAULT_LOCAL_PROMPT_PROFILE_REGISTRY_PATH.read_text, encoding="utf-8"))
    entry = next(item for item in payload["profiles"] if item["profile"]["profile_id"] == "ollama.qwen.chatml.v1")
    entry["profile"]["stop_sequences_by_task_class"]["concise_text"] = stops
    path = tmp_path / "profiles.json"
    await asyncio.to_thread(path.write_text, json.dumps(payload), encoding="utf-8")
    operation = resolve_local_prompting_policy(provider_backend="ollama", model="qwen2.5:7b",
        messages=[{"role": "user", "content": "hello"}], runtime_context={"local_prompt_profile_registry_path": str(path)})
    if stops == ["  PROFILE\n", " "]:
        result = await operation
        assert result.effective_stop_sequences == (*stops, "<|eot_id|>", "</s>")
    else:
        with pytest.raises(ValueError, match="stop_sequences"):
            await operation
