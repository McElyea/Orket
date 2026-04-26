import json
import sys
from pathlib import Path
from typing import Any

import pytest

import orket.settings as settings_module


class OrgBuilder:
    def __init__(self, name: str = "Test Org"):
        self.data = {
            "name": name,
            "vision": "Test Vision",
            "ethos": "Test Ethos",
            "branding": {"design_dos": [], "colorscheme": {}},
            "architecture": {"cicd_rules": [], "preferred_stack": {}, "idesign_threshold": 7},
            "departments": ["core"],
            "contact": {"email": "test@example.com"}
        }

    def with_idesign(self, threshold: int = 7):
        self.data["architecture"]["idesign_threshold"] = threshold
        return self

    def write(self, root: Path):
        config_dir = root / "config"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "organization.json").write_text(json.dumps(self.data), encoding="utf-8")
        # Also write modular ones to avoid ConfigLoader warnings
        (config_dir / "org_info.json").write_text(json.dumps({
            "name": self.data["name"],
            "vision": self.data["vision"],
            "ethos": self.data["ethos"],
            "departments": self.data["departments"],
            "contact": self.data["contact"]
        }), encoding="utf-8")
        (config_dir / "architecture.json").write_text(json.dumps(self.data["architecture"]), encoding="utf-8")
        return self

class IssueBuilder:
    def __init__(self, id: str, summary: str):
        self.data = {
            "id": id,
            "summary": summary,
            "type": "issue",
            "status": "ready",
            "seat": "lead_architect",
            "priority": "Medium",
            "depends_on": []
        }

    def with_status(self, status: str):
        self.data["status"] = status
        return self

    def with_seat(self, seat: str):
        self.data["seat"] = seat
        return self

    def depends_on(self, issue_ids: list[str]):
        self.data["depends_on"] = issue_ids
        return self

    def build(self):
        return self.data

class EpicBuilder:
    def __init__(self, id: str, name: str):
        self.data = {
            "id": id,
            "name": name,
            "type": "epic",
            "team": "standard",
            "environment": "standard",
            "description": "Test Epic",
            "architecture_governance": {"idesign": False, "pattern": "Standard"},
            "issues": []
        }

    def with_issues(self, issues: list[dict[str, Any]]):
        self.data["issues"] = issues
        return self

    def with_idesign(self, enabled: bool = True):
        self.data["architecture_governance"]["idesign"] = enabled
        return self

    def write(self, root: Path, department: str = "core"):
        epic_dir = root / "model" / department / "epics"
        epic_dir.mkdir(parents=True, exist_ok=True)
        (epic_dir / f"{self.data['id']}.json").write_text(json.dumps(self.data), encoding="utf-8")
        return self

class TeamBuilder:
    def __init__(self, name: str = "standard"):
        self.data = {
            "name": name,
            "seats": {
                "lead_architect": {"name": "Lead", "roles": ["lead_architect"]},
                "integrity_guard": {"name": "Guard", "roles": ["integrity_guard"]}
            }
        }

    def write(self, root: Path, department: str = "core"):
        team_dir = root / "model" / department / "teams"
        team_dir.mkdir(parents=True, exist_ok=True)
        (team_dir / f"{self.data['name']}.json").write_text(json.dumps(self.data), encoding="utf-8")
        return self

@pytest.fixture
def test_root(tmp_path):
    root = tmp_path
    # Create standard directory structure
    (root / "config").mkdir()
    for d in ["epics", "roles", "dialects", "teams", "environments"]:
        (root / "model" / "core" / d).mkdir(parents=True)

    # Write default dialects
    for d_name in ["qwen", "llama3", "deepseek-r1", "phi", "generic"]:
        (root / "model" / "core" / "dialects" / f"{d_name}.json").write_text(json.dumps({
            "model_family": d_name, "dsl_format": "JSON", "constraints": [], "hallucination_guard": "None"
        }))

    # Write default roles
    (root / "model" / "core" / "roles" / "lead_architect.json").write_text(json.dumps({
        "id": "ARCH", "summary": "lead_architect", "type": "utility", "description": "D", "tools": ["write_file", "update_issue_status"]
    }))
    (root / "model" / "core" / "roles" / "integrity_guard.json").write_text(json.dumps({
        "id": "VERI", "summary": "integrity_guard", "type": "utility", "description": "V", "tools": ["update_issue_status", "read_file"]
    }))

    # Write default environment
    (root / "model" / "core" / "environments" / "standard.json").write_text(json.dumps({
        "name": "standard", "model": "gpt-4", "temperature": 0.1
    }))

    return root

@pytest.fixture
def workspace(test_root):
    ws = test_root / "workspace"
    ws.mkdir()
    (ws / "agent_output").mkdir()
    (ws / "verification").mkdir()
    return ws

@pytest.fixture
def db_path(test_root):
    return str(test_root / "orket_test.db")


@pytest.fixture
def api_key_env(monkeypatch):
    """Layer: unit. Provides a per-test API key env value for API tests."""
    monkeypatch.setenv("ORKET_API_KEY", "test-key")
    return "test-key"


@pytest.fixture
def test_client(tmp_path, api_key_env):
    """Layer: integration. Provides a fresh API TestClient per test."""
    from fastapi.testclient import TestClient

    from orket.interfaces.api import create_api_app

    client = TestClient(create_api_app(project_root=tmp_path))
    try:
        yield client
    finally:
        client.close()


@pytest.fixture
async def async_engine(tmp_path):
    """Layer: integration. Provides an OrchestrationEngine with teardown."""
    from orket.orchestration.engine import OrchestrationEngine

    engine = OrchestrationEngine(
        workspace_root=tmp_path / "workspace",
        db_path=str(tmp_path / "orket.db"),
        config_root=tmp_path,
    )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.fixture(autouse=True)
async def close_direct_orchestration_engines(monkeypatch):
    """Layer: integration. Closes direct OrchestrationEngine constructions after each test."""
    from orket.orchestration.engine import OrchestrationEngine

    original_init = OrchestrationEngine.__init__
    engines = []

    def tracked_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        engines.append(self)

    monkeypatch.setattr(OrchestrationEngine, "__init__", tracked_init)
    try:
        yield
    finally:
        for engine in reversed(engines):
            await engine.close()


@pytest.fixture(autouse=True)
def fail_closed_sandbox_creation(monkeypatch):
    # The general pytest suite fails closed on Docker sandbox creation.
    # Tests that intentionally exercise live sandbox behavior must opt out.
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")


@pytest.fixture(autouse=True)
def clear_settings_caches_between_tests():
    settings_module.clear_settings_cache()
    yield
    settings_module.clear_settings_cache()


@pytest.fixture
def fresh_runtime_state(monkeypatch):
    """Layer: unit. Provides isolated GlobalState for tests that touch runtime_state."""
    import orket.state as state_module

    fresh = state_module.GlobalState()
    monkeypatch.setattr(state_module, "runtime_state", fresh)
    api_module = sys.modules.get("orket.interfaces.api")
    if api_module is not None:
        monkeypatch.setattr(api_module, "runtime_state", fresh)
    return fresh

