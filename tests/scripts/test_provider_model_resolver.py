# LIFECYCLE: live
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path("scripts/providers/provider_model_resolver.py")
SPEC = importlib.util.spec_from_file_location("provider_model_resolver", MODULE_PATH)
assert SPEC and SPEC.loader
resolver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resolver)  # type: ignore[arg-type]


def test_normalize_provider_maps_lmstudio_to_openai_compat() -> None:
    assert resolver.normalize_provider("lmstudio") == "openai_compat"
    assert resolver.normalize_provider("openai_compat") == "openai_compat"
    assert resolver.normalize_provider("ollama") == "ollama"


def test_choose_model_prefers_exact_match() -> None:
    models = ["qwen3.5-4b", "qwen2.5-coder:7b", "text-embedding-nomic-embed-text-v1.5"]
    assert resolver.choose_model(models, preferred_model="qwen3.5-4b") == "qwen3.5-4b"


def test_rank_models_prefers_coder_and_penalizes_embeddings() -> None:
    models = ["text-embedding-nomic-embed-text-v1.5", "qwen3.5-4b", "qwen2.5-coder:7b"]
    ranked = resolver.rank_models(models)
    assert ranked[0] == "qwen2.5-coder:7b"
    assert ranked[-1] == "text-embedding-nomic-embed-text-v1.5"


def test_choose_model_penalizes_latest_tag_when_equally_scored() -> None:
    models = ["qwen3-coder:latest", "qwen2.5-coder:7b"]
    assert resolver.choose_model(models) == "qwen2.5-coder:7b"


def test_list_provider_models_keeps_requested_alias(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_MODEL_STREAM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")
    monkeypatch.setattr(
        resolver,
        "_list_openai_compat_models",
        lambda **kwargs: ["qwen3.5-4b", "qwen3.5-2b"],
    )
    payload = resolver.list_provider_models(provider="lmstudio", base_url="", timeout_s=1.0, api_key=None)
    assert payload["requested_provider"] == "lmstudio"
    assert payload["canonical_provider"] == "openai_compat"
    assert payload["models"] == ["qwen3.5-4b", "qwen3.5-2b"]
