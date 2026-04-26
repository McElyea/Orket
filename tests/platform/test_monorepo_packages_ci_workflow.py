from __future__ import annotations

from pathlib import Path


def test_monorepo_packages_ci_calver_step_names_dry_run_truthfully() -> None:
    """Layer: contract. Verifies CalVer package CI is named as validation while it keeps dry-run behavior."""
    workflow_text = Path(".gitea/workflows/monorepo-packages-ci.yml").read_text(encoding="utf-8")

    assert "- name: Validate CalVer preview" in workflow_text
    assert "stamp_calver.py" in workflow_text
    assert "--dry-run" in workflow_text
    assert "Stamp version preview (CalVer)" not in workflow_text
