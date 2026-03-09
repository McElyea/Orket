from __future__ import annotations

import pytest

from scripts.companion.companion_matrix_case_selection import expand_case_pairs, parse_provider_model_map


def test_parse_provider_model_map_expands_multi_model_segments() -> None:
    """Layer: unit. Verifies provider-model map parsing expands provider=model1|model2 segments into ordered case pairs."""
    pairs = parse_provider_model_map("ollama=qwen:7b|qwen:14b;lmstudio=qwen:14b")
    assert pairs == [
        {"provider": "ollama", "model": "qwen:7b"},
        {"provider": "ollama", "model": "qwen:14b"},
        {"provider": "lmstudio", "model": "qwen:14b"},
    ]


def test_parse_provider_model_map_rejects_invalid_segments() -> None:
    """Layer: unit. Verifies malformed provider-model map segments fail fast with explicit errors."""
    with pytest.raises(ValueError, match="missing '='"):
        parse_provider_model_map("ollama")


def test_expand_case_pairs_prefers_explicit_provider_model_map() -> None:
    """Layer: unit. Verifies explicit provider-model map takes precedence over providers/models zip inputs."""
    pairs = expand_case_pairs(
        providers=["ollama"],
        models=["qwen:7b"],
        provider_model_map="lmstudio=qwen:14b",
    )
    assert pairs == [{"provider": "lmstudio", "model": "qwen:14b"}]


def test_expand_case_pairs_uses_single_provider_multi_model_expansion() -> None:
    """Layer: unit. Verifies a single provider with multiple model tokens expands to one case per model."""
    pairs = expand_case_pairs(
        providers=["ollama"],
        models=["qwen:7b", "qwen:14b"],
    )
    assert pairs == [
        {"provider": "ollama", "model": "qwen:7b"},
        {"provider": "ollama", "model": "qwen:14b"},
    ]


def test_expand_case_pairs_falls_back_to_provider_model_zip() -> None:
    """Layer: unit. Verifies multi-provider inputs without explicit map use provider/model zip behavior."""
    pairs = expand_case_pairs(
        providers=["ollama", "lmstudio"],
        models=["qwen:7b", "qwen:14b"],
    )
    assert pairs == [
        {"provider": "ollama", "model": "qwen:7b"},
        {"provider": "lmstudio", "model": "qwen:14b"},
    ]
