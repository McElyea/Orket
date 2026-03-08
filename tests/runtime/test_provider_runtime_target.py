from __future__ import annotations

# Layer: contract

import pytest

from orket.runtime import provider_runtime_target as runtime_target


@pytest.mark.asyncio
async def test_resolve_provider_runtime_target_auto_selects_ollama_from_cli_inventory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        runtime_target,
        "_list_installed_ollama_models_sync",
        lambda **_: ["qwen2.5-coder:7b", "llama3.1:8b"],
    )

    result = await runtime_target.resolve_provider_runtime_target(
        provider="ollama",
        requested_model="qwen3.5-coder",
        base_url="http://127.0.0.1:11434",
        timeout_s=5.0,
        auto_select_model=True,
        auto_load_local_model=True,
        model_load_timeout_s=30.0,
        model_ttl_sec=600,
    )

    assert result.inventory_source == "ollama_list"
    assert result.model_id == "qwen2.5-coder:7b"
    assert result.resolution_mode == "auto_selected"
    assert result.status == "OK"


@pytest.mark.asyncio
async def test_resolve_provider_runtime_target_loads_lmstudio_model_when_none_loaded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    load_calls: list[dict[str, object]] = []
    loaded_models = {"value": []}

    monkeypatch.setattr(
        runtime_target,
        "_list_installed_lmstudio_models_sync",
        lambda **_: ["qwen3.5-0.8b", "qwen3.5-4b"],
    )

    def _fake_list_loaded(**_: object) -> list[str]:
        return list(loaded_models["value"])

    def _fake_load(*, model_key: str, timeout_s: float, ttl_sec: int) -> dict[str, object]:
        load_calls.append({"model_key": model_key, "timeout_s": timeout_s, "ttl_sec": ttl_sec})
        loaded_models["value"] = [model_key]
        return {"loaded_model": model_key}

    monkeypatch.setattr(runtime_target, "_list_loaded_lmstudio_model_ids_sync", _fake_list_loaded)
    monkeypatch.setattr(runtime_target, "_load_lmstudio_model_sync", _fake_load)

    result = await runtime_target.resolve_provider_runtime_target(
        provider="lmstudio",
        requested_model="",
        base_url="http://127.0.0.1:1234/v1",
        timeout_s=5.0,
        auto_select_model=True,
        auto_load_local_model=True,
        model_load_timeout_s=30.0,
        model_ttl_sec=600,
    )

    assert result.inventory_source == "lms_cli"
    assert result.model_id == "qwen3.5-4b"
    assert result.resolution_mode == "auto_selected_from_disk"
    assert result.auto_load_attempted is True
    assert result.auto_load_performed is True
    assert load_calls == [{"model_key": "qwen3.5-4b", "timeout_s": 30.0, "ttl_sec": 600}]


@pytest.mark.asyncio
async def test_resolve_provider_runtime_target_blocks_when_lmstudio_auto_load_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime_target, "_list_installed_lmstudio_models_sync", lambda **_: ["qwen3.5-4b"])
    monkeypatch.setattr(runtime_target, "_list_loaded_lmstudio_model_ids_sync", lambda **_: [])

    result = await runtime_target.resolve_provider_runtime_target(
        provider="openai_compat",
        requested_model="qwen3.5-4b",
        base_url="http://127.0.0.1:1234/v1",
        timeout_s=5.0,
        auto_select_model=True,
        auto_load_local_model=False,
        model_load_timeout_s=30.0,
        model_ttl_sec=600,
    )

    assert result.status == "BLOCKED"
    assert result.model_id == "qwen3.5-4b"
    assert result.auto_load_attempted is True
    assert result.auto_load_performed is False
