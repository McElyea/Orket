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
