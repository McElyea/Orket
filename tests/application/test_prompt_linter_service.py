from __future__ import annotations

import json
from pathlib import Path

from orket.application.services.prompt_linter import lint_prompt_file


def test_prompt_linter_reports_json_invalid(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{ bad json", encoding="utf-8")
    violations = lint_prompt_file(path, "role")
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "PL001"
    assert violations[0]["code"] == "JSON_INVALID"


def test_prompt_linter_reports_schema_invalid(tmp_path: Path) -> None:
    path = tmp_path / "architect.json"
    payload = {"summary": "architect"}  # missing required role schema fields
    path.write_text(json.dumps(payload), encoding="utf-8")
    violations = lint_prompt_file(path, "role")
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "PL001"
    assert violations[0]["code"] == "SCHEMA_INVALID"


def test_prompt_linter_reports_canonical_role_structure_drift(tmp_path: Path) -> None:
    path = tmp_path / "architect.json"
    payload = {
        "id": "ARCHITECT",
        "summary": "architect",
        "type": "utility",
        "description": "Architect role.",
        "tools": ["write_file", "update_issue_status"],
        "prompt_metadata": {
            "id": "role.architect",
            "version": "1.0.0",
            "status": "stable",
            "owner": "core",
            "updated_at": "2026-02-15",
            "lineage": {"parent": None},
            "changelog": [{"version": "1.0.0", "date": "2026-02-15", "notes": "initial"}],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    violations = lint_prompt_file(path, "role")
    codes = {item["code"] for item in violations}
    assert "CANONICAL_ROLE_INTENT_MISSING" in codes
    assert "CANONICAL_ROLE_RESPONSIBILITIES_MISSING" in codes
    assert "CANONICAL_ROLE_CONSTRAINTS_MISSING" in codes
