from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from orket.discovery import discover_project_assets, get_engine_recommendations, perform_first_run_onboarding


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


def test_discover_project_assets_anchors_model_root_to_project_root(monkeypatch, tmp_path):
    """Layer: contract. Verifies asset discovery resolves the model root from project root, not caller CWD."""
    captures = {}

    class _FakeLoader:
        def __init__(self, root, department):
            captures["root"] = Path(root)
            captures["department"] = department

        def list_assets(self, asset_type):
            return [f"{asset_type}-fixture"]

    off_root_cwd = tmp_path / "other_cwd"
    off_root_cwd.mkdir()
    monkeypatch.chdir(off_root_cwd)
    monkeypatch.setattr("orket.discovery.ConfigLoader", _FakeLoader)
    monkeypatch.setattr("orket.discovery._default_model_root", lambda: tmp_path / "model")

    assets = discover_project_assets("core")

    assert captures["root"] == tmp_path / "model"
    assert captures["department"] == "core"
    assert assets == {
        "rocks": ["rocks-fixture"],
        "epics": ["epics-fixture"],
        "teams": ["teams-fixture"],
    }


def test_perform_first_run_onboarding_recommends_canonical_card_entrypoint(monkeypatch, capsys):
    """Layer: unit. Verifies onboarding recommends the canonical `--card` command instead of blessing rock execution."""
    monkeypatch.setattr("orket.discovery.load_user_settings", lambda: {})
    monkeypatch.setattr("orket.discovery.save_user_settings", lambda _payload: None)
    monkeypatch.setattr("orket.discovery.log_event", lambda *_args, **_kwargs: None)

    result = perform_first_run_onboarding()
    out = capsys.readouterr().out

    assert result == "first_run_setup"
    assert "canonical card entrypoint" in out
    assert "python main.py --card initialize_orket" in out
    assert "initialization rock" not in out
