from __future__ import annotations

from pathlib import Path

from scripts.governance.check_docs_project_hygiene import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_repo(tmp_path: Path) -> None:
    _write(
        tmp_path / "docs" / "ROADMAP.md",
        """# Orket Roadmap

## Maintenance (Non-Priority)
1. techdebt -- Standing recurring maintenance only.
2. techdebt active cycle `CB03072026` -- next slice `CB-ROP-0`.

## Project Index
| Project | Status | Priority | Canonical Path | Owner | Notes |
|---|---|---|---|---|---|
| techdebt | maintenance | P3-maintenance | `docs/projects/techdebt/` | Orket Core | Standing maintenance lane. |
""",
    )
    _write(tmp_path / "docs" / "projects" / "techdebt" / "README.md", "Status: Active\n")
    _write(
        tmp_path / "docs" / "projects" / "techdebt" / "Recurring-Maintenance-Checklist.md",
        "Status: Active (living document)\n",
    )


def test_check_docs_project_hygiene_allows_active_techdebt_cycle_docs(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(
        tmp_path / "docs" / "projects" / "techdebt" / "CB03072026-claude-behavior-remediation-plan.md",
        "Status: Active\n",
    )

    exit_code = main(["--repo-root", str(tmp_path)])

    assert exit_code == 0


def test_check_docs_project_hygiene_fails_on_completed_doc_left_in_active_techdebt_scope(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(
        tmp_path / "docs" / "projects" / "techdebt" / "CB03072026-claude-behavior-remediation-plan.md",
        "Status: Completed\n",
    )

    exit_code = main(["--repo-root", str(tmp_path)])

    assert exit_code == 1


def test_check_docs_project_hygiene_fails_on_non_active_techdebt_cycle_doc(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    _write(
        tmp_path / "docs" / "projects" / "techdebt" / "OBT03072026-current-state-implementation-plan.md",
        "Status: Active\n",
    )

    exit_code = main(["--repo-root", str(tmp_path)])

    assert exit_code == 1
