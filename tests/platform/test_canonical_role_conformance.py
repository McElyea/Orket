from __future__ import annotations

from pathlib import Path

from orket.application.services.canonical_role_templates import CANONICAL_PIPELINE_ROLES
from orket.application.services.prompt_linter import lint_prompt_file


def test_canonical_role_assets_match_template_contract() -> None:
    roles_dir = Path("model") / "core" / "roles"
    drift_errors: list[str] = []

    for role_name in CANONICAL_PIPELINE_ROLES:
        role_path = roles_dir / f"{role_name}.json"
        assert role_path.exists(), f"Missing canonical role asset: {role_path}"
        violations = lint_prompt_file(role_path, "role")
        canonical_violations = [item for item in violations if str(item.get("rule_id") or "") == "PL006"]
        if canonical_violations:
            codes = sorted({str(item.get("code") or "") for item in canonical_violations})
            drift_errors.append(f"{role_path}: {codes}")

    assert not drift_errors, "Canonical role template drift detected:\n" + "\n".join(drift_errors)
