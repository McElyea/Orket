from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_core_pillars_project(root: Path) -> None:
    docs_root = root / "docs" / "projects" / "core-pillars"
    _write(
        docs_root / "README.md",
        "# Core Pillars Project\n\n## Canonical Docs\n1. `docs/projects/core-pillars/README.md`\n2. `docs/projects/core-pillars/01-REQUIREMENTS.md`\n",
    )
    _write(
        docs_root / "01-REQUIREMENTS.md",
        "# Req\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nBaseline.\n\nSee [README](./README.md).\n",
    )


def _seed_core_pillars_project_strict(root: Path) -> None:
    docs_root = root / "docs" / "projects" / "core-pillars"
    _write(
        docs_root / "README.md",
        "# Core Pillars Project\n\n## Canonical Docs\n"
        "1. `docs/projects/core-pillars/README.md`\n"
        "2. `docs/projects/core-pillars/04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md`\n"
        "3. `docs/projects/core-pillars/05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md`\n"
        "4. `docs/projects/core-pillars/07-API-GENERATION-CONTRACT.md`\n"
        "5. `docs/projects/core-pillars/08-DETAILED-SLICE-EXECUTION-PLAN.md`\n",
    )
    _write(
        docs_root / "04-V1-COMMAND-AND-SAFETY-REQUIREMENTS.md",
        "# Safety\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nSafety.\n\n1. `E_SCOPE_REQUIRED`\n2. A1\n",
    )
    _write(
        docs_root / "05-BUCKET-D-FAILURE-LESSONS-REQUIREMENTS.md",
        "# Bucket D\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nMemory.\n\n1. D1 record-on-fail\n2. `E_DRAFT_FAILURE`\n",
    )
    _write(
        docs_root / "07-API-GENERATION-CONTRACT.md",
        "# API Contract\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nAPI gates.\n\n1. API-1 deterministic output\n",
    )
    _write(
        docs_root / "08-DETAILED-SLICE-EXECUTION-PLAN.md",
        "# Plan\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nPlan.\n\nReferences: `E_SCOPE_REQUIRED`, A1, D1, API-1.\n",
    )


def test_docs_lint_passes_clean_fixture(tmp_path: Path) -> None:
    _seed_core_pillars_project(tmp_path)
    result = subprocess.run(
        ["python", "scripts/docs_lint.py", "--root", str(tmp_path / "docs"), "--project", "core-pillars", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_docs_lint_dl1_broken_link(tmp_path: Path) -> None:
    _seed_core_pillars_project(tmp_path)
    bad = tmp_path / "docs" / "projects" / "core-pillars" / "bad.md"
    _write(
        bad,
        "# Bad\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nBroken.\n\n[broken](./missing.md)\n",
    )
    result = subprocess.run(
        ["python", "scripts/docs_lint.py", "--root", str(tmp_path / "docs"), "--project", "core-pillars", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(row["code"] == "E_DOCS_LINK_MISSING" for row in payload["violations"])


def test_docs_lint_dl2_missing_canonical_file(tmp_path: Path) -> None:
    _seed_core_pillars_project(tmp_path)
    (tmp_path / "docs" / "projects" / "core-pillars" / "01-REQUIREMENTS.md").unlink()
    result = subprocess.run(
        ["python", "scripts/docs_lint.py", "--root", str(tmp_path / "docs"), "--project", "core-pillars", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(row["code"] == "E_DOCS_CANONICAL_MISSING" for row in payload["violations"])


def test_docs_lint_dl3_missing_objective_header(tmp_path: Path) -> None:
    _seed_core_pillars_project(tmp_path)
    broken = tmp_path / "docs" / "projects" / "core-pillars" / "broken_active.md"
    _write(broken, "# Broken\n\nDate: 2026-02-24\nStatus: active\n\n## NotObjective\n")
    result = subprocess.run(
        ["python", "scripts/docs_lint.py", "--root", str(tmp_path / "docs"), "--project", "core-pillars", "--json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(row["code"] == "E_DOCS_HEADER_MISSING" for row in payload["violations"])


def test_docs_lint_strict_crossref_passes_when_tokens_declared(tmp_path: Path) -> None:
    _seed_core_pillars_project_strict(tmp_path)
    result = subprocess.run(
        [
            "python",
            "scripts/docs_lint.py",
            "--root",
            str(tmp_path / "docs"),
            "--project",
            "core-pillars",
            "--strict",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "PASS"


def test_docs_lint_strict_crossref_fails_on_undeclared_token(tmp_path: Path) -> None:
    _seed_core_pillars_project_strict(tmp_path)
    extra = tmp_path / "docs" / "projects" / "core-pillars" / "extra.md"
    _write(
        extra,
        "# Extra\n\nDate: 2026-02-24\nStatus: active\n\n## Objective\nStrict check.\n\nReference undeclared `E_NOT_DECLARED`.\n",
    )
    result = subprocess.run(
        [
            "python",
            "scripts/docs_lint.py",
            "--root",
            str(tmp_path / "docs"),
            "--project",
            "core-pillars",
            "--strict",
            "--json",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(row["code"] == "E_DOCS_CROSSREF_MISSING" for row in payload["violations"])
