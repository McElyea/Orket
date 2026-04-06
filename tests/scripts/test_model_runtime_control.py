# LIFECYCLE: live
from __future__ import annotations

import pytest

from scripts.odr import model_runtime_control as control

pytestmark = pytest.mark.unit


def test_parse_ollama_ps_reads_loaded_model_names() -> None:
    stdout = (
        "NAME                ID              SIZE      PROCESSOR    CONTEXT    UNTIL\n"
        "qwen2.5:7b          abc             6.3 GB    100% GPU     16384      3 seconds from now\n"
        "qwen2.5-coder:7b    def             6.3 GB    100% GPU     16384      1 second from now\n"
    )

    assert control._parse_ollama_ps(stdout) == ["qwen2.5:7b", "qwen2.5-coder:7b"]


def test_release_model_residency_sync_stops_ollama_and_waits_until_unloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    loaded = [["qwen2.5-coder:7b"], []]
    stopped: list[str] = []

    monkeypatch.setattr(
        control,
        "_list_loaded_ollama_models_sync",
        lambda **_: list(loaded.pop(0)),
    )
    monkeypatch.setattr(
        control,
        "_stop_ollama_model_sync",
        lambda *, model_id, timeout_s: stopped.append(str(model_id)),
    )
    monkeypatch.setattr(control.time, "sleep", lambda *_args, **_kwargs: None)

    result = control.release_model_residency_sync(
        provider_name="ollama",
        model_id="qwen2.5-coder:7b",
        timeout_s=5.0,
        poll_interval_s=0.01,
    )

    assert stopped == ["qwen2.5-coder:7b"]
    assert result["status"] == "released"
    assert result["loaded_before"] == ["qwen2.5-coder:7b"]
    assert result["loaded_after"] == []


def test_release_model_residency_sync_clears_lmstudio_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        control,
        "list_loaded_lmstudio_model_ids_sync",
        lambda **_: [],
    )
    monkeypatch.setattr(
        control,
        "clear_loaded_models",
        lambda **kwargs: {"status": "OK", "stage": kwargs["stage"], "remaining": []},
    )

    result = control.release_model_residency_sync(
        provider_name="lmstudio",
        model_id="qwen3.5-4b",
        base_url="http://127.0.0.1:1234/v1",
        timeout_s=5.0,
        poll_interval_s=0.01,
    )

    assert result["status"] == "released"
    assert result["provider"] == "lmstudio"
    assert result["loaded_after"] == []


def test_release_model_residency_sync_reports_unsupported_provider() -> None:
    result = control.release_model_residency_sync(
        provider_name="openai_compat",
        model_id="dummy-model",
        timeout_s=5.0,
        poll_interval_s=0.01,
    )

    assert result["status"] == "unsupported"
    assert result["reason"] == "provider_not_supported"


@pytest.mark.asyncio
async def test_complete_with_transient_provider_threads_explicit_provider_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class _FakeProvider:
        def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            captured.update(kwargs)
            self.provider_name = "lmstudio"
            self.provider_backend = "openai_compat"
            self.openai_base_url = "http://127.0.0.1:1234/v1"
            self.ollama_host = ""
            self.model = "mistralai/magistral-small-2509"

        async def complete(self, messages):  # type: ignore[no-untyped-def]
            _ = messages
            return control.ModelResponse(content="ok", raw={"provider_name": "lmstudio"})

        async def close(self) -> None:
            return None

    async def _fake_release_model_residency(**kwargs):  # type: ignore[no-untyped-def]
        return {"status": "released", **kwargs}

    monkeypatch.setattr(control, "LocalModelProvider", _FakeProvider)
    monkeypatch.setattr(control, "release_model_residency", _fake_release_model_residency)

    response, _latency_ms, release = await control.complete_with_transient_provider(
        model="mistralai/magistral-small-2509",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.1,
        timeout=30,
        provider_name="lmstudio",
        base_url="http://127.0.0.1:1234/v1",
        api_key="local-key",
    )

    assert response.content == "ok"
    assert captured["provider"] == "lmstudio"
    assert captured["base_url"] == "http://127.0.0.1:1234/v1"
    assert captured["api_key"] == "local-key"
    assert release["provider_name"] == "lmstudio"
