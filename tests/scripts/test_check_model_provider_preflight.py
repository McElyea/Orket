# LIFECYCLE: live
from __future__ import annotations

import scripts.providers.check_model_provider_preflight as preflight


def test_lmstudio_preflight_sanitizes_model_cache_pre_and_post(monkeypatch) -> None:
    stages: list[str] = []

    def _fake_clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool):  # noqa: ANN001
        stages.append(stage)
        return {"stage": stage, "status": "OK", "base_url": base_url, "timeout_sec": timeout_sec, "strict": strict}

    monkeypatch.setattr(preflight, "clear_loaded_models", _fake_clear_loaded_models)
    monkeypatch.setattr(
        preflight,
        "warmup_provider_model",
        lambda **_: {
            "status": "OK",
            "inventory_source": "lms_ls",
            "resolution_mode": "requested_loaded",
            "resolved_model": "qwen3.5-4b",
            "available_models": ["qwen3.5-4b"],
            "loaded_models_after": ["qwen3.5-4b"],
        },
    )
    monkeypatch.setattr(
        preflight,
        "list_provider_models",
        lambda **_: {
            "canonical_provider": "openai_compat",
            "base_url": "http://127.0.0.1:1234/v1",
            "models": ["qwen3.5-4b"],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        ["check_model_provider_preflight.py", "--provider", "lmstudio", "--model-id", "qwen3.5-4b"],
    )

    exit_code = preflight.main()
    assert exit_code == 0
    assert stages == ["preflight_pre_run", "preflight_post_run"]


def test_lmstudio_preflight_can_disable_model_cache_sanitation(monkeypatch) -> None:
    calls = {"count": 0}

    def _fake_clear_loaded_models(*, stage: str, base_url: str, timeout_sec: int, strict: bool):  # noqa: ANN001
        calls["count"] += 1
        return {"stage": stage, "status": "OK"}

    monkeypatch.setattr(preflight, "clear_loaded_models", _fake_clear_loaded_models)
    monkeypatch.setattr(
        preflight,
        "warmup_provider_model",
        lambda **_: {
            "status": "OK",
            "inventory_source": "lms_ls",
            "resolution_mode": "requested_loaded",
            "resolved_model": "qwen3.5-4b",
            "available_models": ["qwen3.5-4b"],
            "loaded_models_after": ["qwen3.5-4b"],
        },
    )
    monkeypatch.setattr(
        preflight,
        "list_provider_models",
        lambda **_: {
            "canonical_provider": "openai_compat",
            "base_url": "http://127.0.0.1:1234/v1",
            "models": ["qwen3.5-4b"],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_model_provider_preflight.py",
            "--provider",
            "lmstudio",
            "--model-id",
            "qwen3.5-4b",
            "--no-sanitize-model-cache",
        ],
    )

    exit_code = preflight.main()
    assert exit_code == 0
    assert calls["count"] == 0


def test_lmstudio_preflight_runs_runtime_warmup_before_preflight(monkeypatch) -> None:
    warmup_calls: list[dict[str, object]] = []

    monkeypatch.setattr(preflight, "clear_loaded_models", lambda **kwargs: {"stage": kwargs["stage"], "status": "OK"})
    monkeypatch.setattr(preflight, "_stream_smoke_openai_compat", lambda **kwargs: (True, ""))
    monkeypatch.setattr(
        preflight,
        "warmup_provider_model",
        lambda **kwargs: warmup_calls.append(dict(kwargs)) or {
            "status": "OK",
            "inventory_source": "lms_ls",
            "resolution_mode": "auto_selected_from_disk",
            "resolved_model": "qwen3.5-0.8b",
            "available_models": ["qwen3.5-0.8b"],
            "loaded_models_after": ["qwen3.5-0.8b"],
        },
    )
    monkeypatch.setattr(
        preflight,
        "list_provider_models",
        lambda **_: {
            "canonical_provider": "openai_compat",
            "base_url": "http://127.0.0.1:1234/v1",
            "models": ["qwen3.5-0.8b"],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_model_provider_preflight.py",
            "--provider",
            "lmstudio",
            "--smoke-stream",
            "--auto-select-model",
        ],
    )

    exit_code = preflight.main()

    assert exit_code == 0
    assert warmup_calls[0]["provider"] == "lmstudio"
    assert warmup_calls[0]["auto_select_model"] is True
    assert warmup_calls[0]["auto_load_local_model"] is True
