import pytest
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from orket.schema import OrganizationConfig, EpicConfig, IssueConfig, TeamConfig, CardStatus, CardType

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
    
    def depends_on(self, issue_ids: List[str]):
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

    def with_issues(self, issues: List[Dict[str, Any]]):
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
