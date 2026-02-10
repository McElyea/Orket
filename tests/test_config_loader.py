import pytest
import json
from pathlib import Path
from orket.orket import ConfigLoader
from orket.schema import EpicConfig, OrganizationConfig

def test_load_organization(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    org_data = {
        "name": "Test Org",
        "vision": "To test",
        "ethos": "Honesty",
        "branding": {"colorscheme": {"primary": "#000"}},
        "architecture": {"idesign_threshold": 5},
        "contact": {"email": "test@example.com"},
        "departments": ["core"]
    }
    
    (config_dir / "organization.json").write_text(json.dumps(org_data), encoding="utf-8")
    
    loader = ConfigLoader(tmp_path)
    org = loader.load_organization()
    
    assert org is not None
    assert org.name == "Test Org"
    assert org.architecture.idesign_threshold == 5

def test_load_asset_epic(tmp_path):
    model_dir = tmp_path / "model" / "core" / "epics"
    model_dir.mkdir(parents=True)
    
    epic_data = {
        "id": "EPIC-01",
        "name": "Test Epic",
        "team": "team-a",
        "environment": "env-a",
        "issues": []
    }
    
    (model_dir / "test-epic.json").write_text(json.dumps(epic_data), encoding="utf-8")
    
    loader = ConfigLoader(tmp_path)
    epic = loader.load_asset("epics", "test-epic", EpicConfig)
    
    assert epic.id == "EPIC-01"
    assert epic.name == "Test Epic"

def test_list_assets(tmp_path):
    config_dir = tmp_path / "config" / "epics"
    config_dir.mkdir(parents=True)
    (config_dir / "epic1.json").write_text("{}", encoding="utf-8")
    (config_dir / "epic2.json").write_text("{}", encoding="utf-8")
    
    loader = ConfigLoader(tmp_path)
    assets = loader.list_assets("epics")
    
    assert assets == ["epic1", "epic2"]

def test_load_department(tmp_path):
    config_dir = tmp_path / "config" / "departments"
    config_dir.mkdir(parents=True)
    
    dept_data = {
        "name": "Engineering",
        "description": "Building stuff"
    }
    (config_dir / "engineering.json").write_text(json.dumps(dept_data), encoding="utf-8")
    
    loader = ConfigLoader(tmp_path)
    dept = loader.load_department("engineering")
    
    assert dept.name == "Engineering"
