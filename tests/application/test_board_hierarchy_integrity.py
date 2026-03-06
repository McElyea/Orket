from __future__ import annotations

from dataclasses import dataclass

from orket.board import get_board_hierarchy
from orket.exceptions import CardNotFound


@dataclass
class _Issue:
    id: str
    name: str

    def model_dump(self, by_alias: bool = True):
        return {"id": self.id, "summary": self.name}


@dataclass
class _Epic:
    name: str
    description: str
    status: str
    issues: list[_Issue]


@dataclass
class _Rock:
    name: str
    description: str
    status: str
    epics: list[dict[str, str]]


def test_get_board_hierarchy_marks_partial_success_on_load_failures(monkeypatch):
    """Layer: contract. Verifies integrity load failures are explicit and partial-success is surfaced."""
    loads = {
        ("core", "rocks", "rock_ok"): _Rock("rock_ok", "ok", "on_track", [{"epic": "epic_ok", "department": "core"}]),
        ("core", "rocks", "rock_missing"): CardNotFound("missing rock"),
        ("core", "epics", "epic_ok"): _Epic("epic_ok", "ok", "planning", [_Issue("ISS-1", "Issue one")]),
        ("core", "epics", "epic_missing"): FileNotFoundError("missing epic"),
        ("core", "issues", "ISS-1"): _Issue("ISS-1", "Issue one"),
        ("core", "issues", "ISS-MISSING"): ValueError("broken issue"),
    }
    lists = {
        "core": {
            "rocks": ["rock_ok", "rock_missing"],
            "epics": ["epic_ok", "epic_missing"],
            "issues": ["ISS-1", "ISS-MISSING"],
        }
    }

    class _FakeLoader:
        def __init__(self, _root, department):
            self.department = str(department)

        def list_assets(self, asset_type):
            return list(lists[self.department][asset_type])

        def load_asset(self, asset_type, asset_name, _schema):
            value = loads[(self.department, asset_type, asset_name)]
            if isinstance(value, Exception):
                raise value
            return value

    monkeypatch.setattr("orket.board.ConfigLoader", _FakeLoader)

    hierarchy = get_board_hierarchy("core")

    assert hierarchy["result_status"] == "partial_success"
    assert len(hierarchy["load_failures"]) == 3
    assert any(item["stage"] == "rock_load" for item in hierarchy["load_failures"])
    assert any(item["stage"] == "orphan_epic_load" for item in hierarchy["load_failures"])
    assert any(item["stage"] == "issue_load" for item in hierarchy["load_failures"])
    assert any("Partial board load" in alert["message"] for alert in hierarchy["alerts"])


def test_get_board_hierarchy_prefers_issue_id_for_reference_matching(monkeypatch):
    """Layer: contract. Verifies orphan detection uses stable issue IDs before fallback names."""
    loads = {
        ("core", "rocks", "rock_ok"): _Rock("rock_ok", "ok", "on_track", [{"epic": "epic_ok", "department": "core"}]),
        ("core", "epics", "epic_ok"): _Epic("epic_ok", "ok", "planning", [_Issue("ISS-123", "Original summary")]),
        ("core", "issues", "standalone_file"): _Issue("ISS-123", "Renamed summary"),
    }
    lists = {
        "core": {
            "rocks": ["rock_ok"],
            "epics": ["epic_ok"],
            "issues": ["standalone_file"],
        }
    }

    class _FakeLoader:
        def __init__(self, _root, department):
            self.department = str(department)

        def list_assets(self, asset_type):
            return list(lists[self.department][asset_type])

        def load_asset(self, asset_type, asset_name, _schema):
            value = loads[(self.department, asset_type, asset_name)]
            if isinstance(value, Exception):
                raise value
            return value

    monkeypatch.setattr("orket.board.ConfigLoader", _FakeLoader)

    hierarchy = get_board_hierarchy("core")

    assert hierarchy["result_status"] == "success"
    assert hierarchy["load_failures"] == []
    assert hierarchy["orphaned_issues"] == []
