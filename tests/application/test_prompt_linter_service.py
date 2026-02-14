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
