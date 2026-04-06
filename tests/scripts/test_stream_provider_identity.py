# LIFECYCLE: live
from __future__ import annotations

# Layer: contract
import scripts.streaming.run_provider_scenario_direct as direct_script
import scripts.streaming.run_stream_scenario as api_script


def test_direct_provider_identity_prefers_observed_resolved_model(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "lmstudio")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "qwen3.5-coder")

    payload = direct_script._provider_identity(resolved_model_id="qwen3.5-4b")

    assert payload["provider_name"] == "openai_compat"
    assert payload["provider_model_id"] == "qwen3.5-4b"
    assert payload["model_id"] == "qwen3.5-4b"


def test_api_provider_identity_prefers_observed_resolved_model(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_PROVIDER", "real")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_PROVIDER", "ollama")
    monkeypatch.setenv("ORKET_MODEL_STREAM_REAL_MODEL_ID", "qwen3.5-coder")

    payload = api_script._provider_identity(resolved_model_id="qwen2.5-coder:7b")

    assert payload["provider_name"] == "ollama"
    assert payload["provider_model_id"] == "qwen2.5-coder:7b"
