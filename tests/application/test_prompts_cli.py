from __future__ import annotations

import json
from pathlib import Path

from orket.interfaces.prompts_cli import (
    lint_prompt_assets,
    list_prompts,
    resolve_prompt,
    update_prompt_metadata,
    validate_prompt_assets,
)


def _seed_assets(root: Path) -> None:
    roles = root / "model" / "core" / "roles"
    dialects = root / "model" / "core" / "dialects"
    roles.mkdir(parents=True, exist_ok=True)
    dialects.mkdir(parents=True, exist_ok=True)

    role_payload = {
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
            "updated_at": "2026-02-14",
            "lineage": {"parent": None},
            "changelog": [{"version": "1.0.0", "date": "2026-02-14", "notes": "initial"}],
        },
    }
    dialect_payload = {
        "model_family": "generic",
        "dsl_format": "{\"tool\":\"write_file\",\"args\":{\"path\":\"a\",\"content\":\"b\"}}",
        "constraints": ["Return JSON only."],
        "hallucination_guard": "No extra prose",
        "system_prefix": "",
        "tool_call_syntax": "openai_compatible",
        "style_guidelines": [],
        "prompt_metadata": {
            "id": "dialect.generic",
            "version": "1.0.0",
            "status": "stable",
            "owner": "core",
            "updated_at": "2026-02-14",
            "lineage": {"parent": None},
            "changelog": [{"version": "1.0.0", "date": "2026-02-14", "notes": "initial"}],
        },
    }
    (roles / "architect.json").write_text(json.dumps(role_payload, indent=2), encoding="utf-8")
    (dialects / "generic.json").write_text(json.dumps(dialect_payload, indent=2), encoding="utf-8")


def test_validate_prompt_assets_core_passes() -> None:
    errors = validate_prompt_assets(Path("."))
    assert errors == []


def test_list_and_resolve_prompt(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    rows = list_prompts(tmp_path, kind="all")
    ids = {row["id"] for row in rows}
    assert "role.architect" in ids
    assert "dialect.generic" in ids

    resolved = resolve_prompt(
        tmp_path,
        role="architect",
        dialect="generic",
        selection_policy="stable",
        strict=True,
    )
    assert resolved["metadata"]["prompt_id"] == "role.architect+dialect.generic"
    assert resolved["metadata"]["selection_policy"] == "stable"


def test_update_prompt_metadata_lifecycle(tmp_path: Path) -> None:
    _seed_assets(tmp_path)

    preview = update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=False,
    )
    assert preview["after"]["version"] == "1.1.0"
    assert preview["after"]["status"] == "candidate"

    applied = update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )
    assert applied["after"]["version"] == "1.1.0"

    promoted = update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="promote",
        status="stable",
        notes="promoted stable",
        apply_changes=True,
    )
    assert promoted["after"]["status"] == "stable"

    deprecated = update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="deprecate",
        notes="retired",
        apply_changes=True,
    )
    assert deprecated["after"]["status"] == "deprecated"


def test_lint_prompt_assets_reports_placeholder_contracts(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    role_path = tmp_path / "model" / "core" / "roles" / "architect.json"
    payload = json.loads(role_path.read_text(encoding="utf-8"))
    payload["description"] = "Implement {{project_name}} and {{missing_placeholder}}."
    payload["prompt_metadata"]["placeholders"] = ["project_name", "unused_placeholder"]
    role_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lint = lint_prompt_assets(tmp_path)
    codes = {item["code"] for item in lint["violations"]}
    assert "PLACEHOLDER_UNDECLARED" in codes
    assert "PLACEHOLDER_UNUSED" in codes
    assert lint["error_count"] >= 1
    assert lint["warning_count"] >= 1
