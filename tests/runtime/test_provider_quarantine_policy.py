from __future__ import annotations

from orket.runtime.provider_quarantine_policy import (
    is_model_quarantined,
    is_provider_quarantined,
    parse_quarantined_provider_models,
    parse_quarantined_providers,
    resolve_provider_quarantine_policy,
)


# Layer: unit
def test_parse_quarantined_providers_normalizes_tokens() -> None:
    assert parse_quarantined_providers("ollama, LMSTUDIO ,openai_compat") == {
        "ollama",
        "lmstudio",
        "openai_compat",
    }


# Layer: contract
def test_parse_quarantined_provider_models_supports_model_ids_with_colons() -> None:
    rows = parse_quarantined_provider_models("ollama:qwen2.5-coder:7b,lmstudio:qwen3.5-4b")
    assert rows == {("ollama", "qwen2.5-coder:7b"), ("lmstudio", "qwen3.5-4b")}


# Layer: contract
def test_resolve_provider_quarantine_policy_reads_environment() -> None:
    payload = resolve_provider_quarantine_policy(
        environment={
            "ORKET_PROVIDER_QUARANTINE": "ollama",
            "ORKET_PROVIDER_MODEL_QUARANTINE": "openai_compat:gpt-4o-mini",
        }
    )
    assert payload["providers"] == ["ollama"]
    assert payload["provider_models"] == [("openai_compat", "gpt-4o-mini")]


# Layer: contract
def test_provider_and_model_quarantine_checks_are_provider_aware() -> None:
    assert is_provider_quarantined(
        requested_provider="lmstudio",
        canonical_provider="openai_compat",
        quarantined_providers={"openai_compat"},
    )
    assert is_model_quarantined(
        requested_provider="lmstudio",
        canonical_provider="openai_compat",
        model_id="qwen3.5-4b",
        quarantined_provider_models={("openai_compat", "qwen3.5-4b")},
    )
