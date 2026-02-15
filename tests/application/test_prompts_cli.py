from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from orket.interfaces.prompts_cli import (
    enforce_candidate_prompt_sla,
    find_stale_candidate_prompts,
    lint_prompt_assets,
    list_prompts,
    resolve_prompt,
    show_prompt,
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
        "name": "architect",
        "type": "utility",
        "description": "Architect role.",
        "intent": "Produce architecture decisions and implementation guidance.",
        "responsibilities": [
            "Read requirements context and existing artifacts.",
            "Write design decisions to agent_output/design.txt.",
            "Set status to code_review after design updates.",
        ],
        "constraints": [
            "Do not skip required design artifact updates.",
        ],
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


def test_update_prompt_metadata_rejects_direct_draft_to_stable_promotion(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="draft",
        notes="new draft",
        apply_changes=True,
    )
    try:
        update_prompt_metadata(
            tmp_path,
            prompt_id="role.architect",
            mode="promote",
            status="stable",
            notes="bad promote",
            apply_changes=True,
        )
        assert False, "Expected ValueError for draft->stable transition"
    except ValueError as exc:
        assert "Invalid status transition: draft -> stable" in str(exc)


def test_update_prompt_metadata_rejects_promotion_when_report_fails(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )

    try:
        update_prompt_metadata(
            tmp_path,
            prompt_id="role.architect",
            mode="promote",
            status="stable",
            notes="promote stable",
            promotion_report={
                "pass": False,
                "blockers": [{"code": "CRITERIA_CANDIDATE_GUARD_PASS_RATE_MIN"}],
            },
            apply_changes=True,
        )
        assert False, "Expected ValueError when promotion report fails"
    except ValueError as exc:
        assert "Promotion criteria not met for stable." in str(exc)
        assert "CRITERIA_CANDIDATE_GUARD_PASS_RATE_MIN" in str(exc)


def test_update_prompt_metadata_allows_promotion_when_report_passes(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )
    promoted = update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="promote",
        status="stable",
        notes="promote stable",
        promotion_report={"pass": True, "blockers": []},
        apply_changes=True,
    )
    assert promoted["after"]["status"] == "stable"


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


def test_find_stale_candidate_prompts_detects_age_threshold(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )
    rows = find_stale_candidate_prompts(
        tmp_path,
        max_candidate_age_days=14,
        as_of=date.fromisoformat("2026-03-10"),
    )
    assert len(rows) == 1
    assert rows[0]["id"] == "role.architect"
    assert rows[0]["stale"] is True


def test_enforce_candidate_prompt_sla_auto_deprecates_stale_candidates(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )
    result = enforce_candidate_prompt_sla(
        tmp_path,
        max_candidate_age_days=14,
        as_of=date.fromisoformat("2026-03-10"),
        apply_changes=True,
    )
    assert result["ok"] is True
    assert result["deprecate_count"] == 1
    role_payload = show_prompt(tmp_path, "role.architect")["payload"]
    assert role_payload["prompt_metadata"]["status"] == "deprecated"


def test_enforce_candidate_prompt_sla_renews_explicit_prompt_ids(tmp_path: Path) -> None:
    _seed_assets(tmp_path)
    update_prompt_metadata(
        tmp_path,
        prompt_id="role.architect",
        mode="new",
        version="1.1.0",
        status="candidate",
        notes="candidate cut",
        apply_changes=True,
    )
    result = enforce_candidate_prompt_sla(
        tmp_path,
        max_candidate_age_days=14,
        renew_ids=["role.architect"],
        as_of=date.fromisoformat("2026-03-10"),
        apply_changes=True,
    )
    assert result["ok"] is True
    assert result["renew_count"] == 1
    role_payload = show_prompt(tmp_path, "role.architect")["payload"]
    assert role_payload["prompt_metadata"]["status"] == "candidate"
