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


def test_llama_cpp_preflight_uses_openai_compat_listing_without_lmstudio_sanitation(monkeypatch) -> None:
    stages: list[str] = []

    def _fake_clear_loaded_models(**kwargs):  # noqa: ANN001
        stages.append(str(kwargs["stage"]))
        return {"stage": kwargs["stage"], "status": "OK"}

    monkeypatch.setattr(preflight, "clear_loaded_models", _fake_clear_loaded_models)
    monkeypatch.setattr(
        preflight,
        "warmup_provider_model",
        lambda **_: {
            "status": "OK",
            "inventory_source": "http_models+gguf_inventory",
            "resolution_mode": "requested",
            "resolved_model": "qwen3.6-27b-q4_k_m",
            "available_models": ["qwen3.6-27b-q4_k_m"],
            "loaded_models_after": [],
        },
    )
    monkeypatch.setattr(
        preflight,
        "list_provider_models",
        lambda **_: {
            "canonical_provider": "openai_compat",
            "base_url": "http://127.0.0.1:8080/v1",
            "models": ["qwen3.6-27b-q4_k_m"],
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_model_provider_preflight.py",
            "--provider",
            "llama_cpp",
            "--model-id",
            "qwen3.6-27b-q4_k_m",
        ],
    )

    exit_code = preflight.main()

    assert exit_code == 0
    assert stages == []


def test_llama_cpp_preflight_fails_when_warmup_blocks(monkeypatch) -> None:
    monkeypatch.setattr(
        preflight,
        "warmup_provider_model",
        lambda **_: {
            "status": "BLOCKED",
            "inventory_source": "http_models+gguf_inventory",
            "resolution_mode": "gguf_inventory_empty",
            "resolved_model": "qwen3.6-27b-q4_k_m",
            "available_models": ["qwen3.6-27b-q4_k_m"],
            "loaded_models_after": [],
        },
    )
    monkeypatch.setattr(
        preflight,
        "list_provider_models",
        lambda **_: (_ for _ in ()).throw(AssertionError("blocked warmup should stop before listing")),
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_model_provider_preflight.py",
            "--provider",
            "llama_cpp",
            "--model-id",
            "qwen3.6-27b-q4_k_m",
        ],
    )

    assert preflight.main() == 1


def test_llama_cpp_preflight_reports_unreachable_warmup_without_traceback(monkeypatch) -> None:
    def _raise_connect(**_: object) -> dict[str, object]:
        raise preflight.httpx.ConnectError("no listener")

    monkeypatch.setattr(preflight, "warmup_provider_model", _raise_connect)
    monkeypatch.setattr(
        "sys.argv",
        [
            "check_model_provider_preflight.py",
            "--provider",
            "llama_cpp",
            "--model-id",
            "qwen3.6-27b-q4_k_m",
        ],
    )

    assert preflight.main() == 1
