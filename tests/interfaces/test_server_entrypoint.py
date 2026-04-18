from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import orket.runtime as runtime_module
import orket.settings as settings_module


def test_server_entrypoint_bootstraps_repo_env_before_app_creation(monkeypatch) -> None:
    """Layer: contract. Verifies python server.py loads the Orket repo .env before app construction."""
    captured: dict[str, Any] = {}

    def fake_load_env() -> None:
        captured["env_file"] = settings_module.ENV_FILE

    def fake_create_api_app(config: Any) -> object:
        captured["project_root"] = config.project_root
        return object()

    monkeypatch.setattr(settings_module, "load_env", fake_load_env)
    monkeypatch.setattr(runtime_module, "create_api_app", fake_create_api_app)
    sys.modules.pop("server", None)

    server_module = importlib.import_module("server")
    project_root = Path(server_module.__file__).resolve().parent

    assert captured["env_file"] == project_root / ".env"
    assert captured["project_root"] == project_root
