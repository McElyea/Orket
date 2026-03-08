from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from orket.driver import OrketDriver


class _AlwaysMissingLoader:
    def __init__(self, *_args, **_kwargs):
        return None

    def load_asset(self, asset_kind, asset_name, _schema):
        raise FileNotFoundError(f"missing {asset_kind}/{asset_name}")


def test_load_engine_configs_marks_degraded_and_emits_mode_event(monkeypatch):
    """Layer: contract. Verifies explicit degradation markers and telemetry for config load failures."""
    events = []

    def _capture(event_name, payload, *args, **kwargs):
        events.append((event_name, payload))

    monkeypatch.setattr("orket.driver.ConfigLoader", _AlwaysMissingLoader)
    monkeypatch.setattr("orket.driver.log_event", _capture)
    driver = OrketDriver.__new__(OrketDriver)
    driver.provider = SimpleNamespace(model="qwen2.5-coder")
    driver.strict_config_mode = False
    driver.config_degraded = False
    driver.config_dependency_classification = {}
    driver.config_load_failures = []

    driver._load_engine_configs()

    assert driver.prompting_mode == "fallback"
    assert driver.config_degraded is True
    assert driver.config_dependency_classification["skill.operations_lead"] == "degradable"
    assert driver.config_dependency_classification["dialect.qwen"] == "degradable"
    assert any(name == "driver_config_dependency_failed" for name, _ in events)
    assert any(name == "driver_prompting_mode" and payload["mode"] == "fallback" for name, payload in events)


def test_load_engine_configs_strict_mode_fails_closed(monkeypatch):
    """Layer: unit. Verifies strict mode blocks fallback prompting on missing config assets."""
    monkeypatch.setattr("orket.driver.ConfigLoader", _AlwaysMissingLoader)
    monkeypatch.setattr("orket.driver.log_event", lambda *_args, **_kwargs: None)
    driver = OrketDriver.__new__(OrketDriver)
    driver.provider = SimpleNamespace(model="llama3.1")
    driver.strict_config_mode = True
    driver.config_degraded = False
    driver.config_dependency_classification = {}
    driver.config_load_failures = []

    with pytest.raises(RuntimeError, match="strict config mode"):
        driver._load_engine_configs()


def test_driver_init_anchors_default_paths_to_project_root(monkeypatch, tmp_path):
    """Layer: contract. Verifies default driver roots are resolved from project root, not caller CWD."""
    captures = {}

    class _FakeFileTools:
        def __init__(self, root):  # type: ignore[no-untyped-def]
            captures["fs_root"] = Path(root)

    class _FakeReforgerTools:
        def __init__(self, workspace, allowed_roots):  # type: ignore[no-untyped-def]
            captures["workspace_root"] = Path(workspace)
            captures["allowed_roots"] = [Path(item) for item in allowed_roots]

    class _FakeProvider:
        def __init__(self, model, temperature=0.1):  # type: ignore[no-untyped-def]
            self.model = model

    class _FakeSelector:
        def __init__(self, organization=None):  # type: ignore[no-untyped-def]
            _ = organization

        def select(self, role, override=None):  # type: ignore[no-untyped-def]
            _ = role
            return override or "qwen3.5-coder"

    def _fake_load_engine_configs(self) -> None:
        self.skill = None
        self.dialect = None
        self.prompting_mode = "fallback"
        self.config_degraded = False
        self.config_dependency_classification = {}
        self.config_load_failures = []

    off_root_cwd = tmp_path / "other_cwd"
    off_root_cwd.mkdir()
    monkeypatch.chdir(off_root_cwd)
    monkeypatch.setattr("orket.driver._default_project_root", lambda: tmp_path)
    monkeypatch.setattr("orket.driver.AsyncFileTools", _FakeFileTools)
    monkeypatch.setattr("orket.driver.ReforgerTools", _FakeReforgerTools)
    monkeypatch.setattr("orket.driver.LocalModelProvider", _FakeProvider)
    monkeypatch.setattr("orket.orchestration.models.ModelSelector", _FakeSelector)
    monkeypatch.setattr(OrketDriver, "_load_engine_configs", _fake_load_engine_configs)

    driver = OrketDriver(model="qwen3.5-coder")

    assert driver.project_root == tmp_path
    assert driver.model_root == tmp_path / "model"
    assert driver.workspace_root == tmp_path / "workspace" / "default"
    assert captures["fs_root"] == tmp_path
    assert captures["workspace_root"] == tmp_path / "workspace" / "default"
    assert captures["allowed_roots"] == [tmp_path]
