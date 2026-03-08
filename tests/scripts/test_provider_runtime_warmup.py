from __future__ import annotations

import scripts.providers.provider_runtime_warmup as warmup


# Layer: contract


def test_warmup_provider_model_delegates_to_shared_runtime_target(monkeypatch) -> None:
    seen: dict[str, object] = {}
    monkeypatch.setattr(
        warmup,
        "resolve_provider_runtime_target_sync",
        lambda **kwargs: seen.update(kwargs) or {
            "requested_provider": "lmstudio",
            "canonical_provider": "openai_compat",
            "requested_model": "qwen3.5-coder",
            "model_id": "qwen3.5-4b",
            "base_url": "http://127.0.0.1:1234/v1",
            "resolution_mode": "auto_selected_from_disk",
            "inventory_source": "lms_cli",
            "available_models": ["qwen3.5-0.8b", "qwen3.5-4b"],
            "loaded_models_before": [],
            "loaded_models_after": ["qwen3.5-4b"],
            "auto_load_attempted": True,
            "auto_load_performed": True,
            "status": "OK",
        },
    )

    result = warmup.warmup_provider_model(
        provider="lmstudio",
        requested_model="qwen3.5-coder",
        base_url="http://127.0.0.1:1234/v1",
        timeout_s=5.0,
        auto_select_model=True,
        auto_load_local_model=True,
        model_load_timeout_s=30.0,
        model_ttl_sec=600,
    )

    assert seen["provider"] == "lmstudio"
    assert seen["requested_model"] == "qwen3.5-coder"
    assert seen["auto_select_model"] is True
    assert result["model_id"] == "qwen3.5-4b"
    assert result["auto_load_performed"] is True
