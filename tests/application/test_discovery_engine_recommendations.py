from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from orket.discovery import get_engine_recommendations


def _patch_engine_registry(monkeypatch, payload: dict) -> None:
    class _FakeFS:
        def __init__(self, _root):
            return None

        def read_file_sync(self, _path):
            return json.dumps(payload)

    original_exists = Path.exists

    def _exists(path_obj):
        path_text = str(path_obj).replace("\\", "/").lower()
        if path_text.endswith("model/core/engines.json"):
            return True
        return original_exists(path_obj)

    monkeypatch.setattr("orket.discovery.AsyncFileTools", _FakeFS)
    monkeypatch.setattr(Path, "exists", _exists)
    monkeypatch.setattr("orket.hardware.get_current_profile", lambda: SimpleNamespace(vram_gb=24.0, ram_gb=64.0, cpu_cores=16))
    monkeypatch.setattr("orket.hardware.can_handle_model_tier", lambda _tier, _profile: True)


def test_get_engine_recommendations_skips_when_highest_installed(monkeypatch):
    """Layer: unit. Verifies no upgrade suggestion when installed model already meets top catalog tier."""
    payload = {
        "name": "test",
        "updated_at": "2026-01-01",
        "mappings": {
            "coder": {
                "tier": "mid",
                "keywords": ["coder"],
                "fallback": "fallback-coder",
                "catalog": [
                    {"model": "qwen2.5-coder-7b", "tier": "base", "description": "base"},
                    {"model": "qwen2.5-coder-14b", "tier": "mid", "description": "mid"},
                ],
            }
        },
    }
    _patch_engine_registry(monkeypatch, payload)
    monkeypatch.setattr("orket.discovery.get_installed_models", lambda: ["qwen2.5-coder-14b"])

    recommendations = get_engine_recommendations()

    assert recommendations == []


def test_get_engine_recommendations_suggests_higher_missing_tier(monkeypatch):
    """Layer: unit. Verifies higher-tier suggestion when installed model is below available catalog tier."""
    payload = {
        "name": "test",
        "updated_at": "2026-01-01",
        "mappings": {
            "coder": {
                "tier": "mid",
                "keywords": ["coder"],
                "fallback": "fallback-coder",
                "catalog": [
                    {"model": "qwen2.5-coder-7b", "tier": "base", "description": "base"},
                    {"model": "qwen2.5-coder-14b", "tier": "mid", "description": "mid"},
                ],
            }
        },
    }
    _patch_engine_registry(monkeypatch, payload)
    monkeypatch.setattr("orket.discovery.get_installed_models", lambda: ["qwen2.5-coder-7b"])

    recommendations = get_engine_recommendations()

    assert len(recommendations) == 1
    assert recommendations[0]["category"] == "coder"
    assert recommendations[0]["suggestion"] == "qwen2.5-coder-14b"
    assert recommendations[0]["tier"] == "mid"
