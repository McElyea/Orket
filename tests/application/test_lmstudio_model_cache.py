from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType


def _load_script_module(module_name: str, script_path: str) -> ModuleType:
    path = Path(script_path)
    scripts_dir = str(path.parent.resolve())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:  # noqa: ANN001
        return False

    def read(self) -> bytes:
        return self._payload


def test_clear_loaded_models_unloads_all_instances(monkeypatch) -> None:
    module = _load_script_module("lmstudio_model_cache_clear", "scripts/providers/lmstudio_model_cache.py")
    loaded_instances = ["qwen3.5-2b:1", "qwen3.5-4b:2"]

    def _fake_urlopen(request, timeout=0):  # noqa: ANN001, ANN003
        del timeout
        method = request.get_method()
        url = str(request.full_url)
        if method == "GET" and url.endswith("/api/v1/models"):
            return _FakeResponse(
                {
                    "models": [
                        {
                            "key": "qwen3.5",
                            "loaded_instances": [{"id": token} for token in loaded_instances],
                        }
                    ]
                }
            )
        if method == "POST" and url.endswith("/api/v1/models/unload"):
            payload = json.loads((request.data or b"{}").decode("utf-8"))
            instance_id = str(payload.get("instance_id") or "")
            if instance_id in loaded_instances:
                loaded_instances.remove(instance_id)
            return _FakeResponse({"status": "ok"})
        raise AssertionError(f"unexpected request: {method} {url}")

    monkeypatch.setattr(module, "urlopen", _fake_urlopen)

    result = module.clear_loaded_models(
        stage="pre_run",
        base_url="http://127.0.0.1:1234/v1",
        timeout_sec=5,
        strict=True,
    )

    assert result["status"] == "OK"
    assert result["loaded_before"] == ["qwen3.5-2b:1", "qwen3.5-4b:2"]
    assert result["unloaded"] == ["qwen3.5-2b:1", "qwen3.5-4b:2"]
    assert result["remaining"] == []
    assert result["api_models_url"] == "http://127.0.0.1:1234/api/v1/models"
    assert result["unload_url"] == "http://127.0.0.1:1234/api/v1/models/unload"


def test_default_lmstudio_base_url_prefers_env(monkeypatch) -> None:
    module = _load_script_module("lmstudio_model_cache_env", "scripts/providers/lmstudio_model_cache.py")
    monkeypatch.setenv("ORKET_LMSTUDIO_BASE_URL", "http://localhost:1234/custom")
    monkeypatch.setenv("ORKET_LLM_OPENAI_BASE_URL", "http://127.0.0.1:1234/v1")

    assert module.default_lmstudio_base_url() == "http://localhost:1234/custom"

