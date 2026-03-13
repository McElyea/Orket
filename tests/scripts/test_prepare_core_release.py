from __future__ import annotations

import subprocess
from pathlib import Path

from scripts.governance.prepare_core_release import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8"))


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def _replace(path: Path, old: str, new: str) -> None:
    _write(path, _read(path).replace(old, new))


def _pyproject_text(version: str) -> str:
    return f"""[project]
name = "orket"
version = "{version}"
"""


def _changelog_text(version: str) -> str:
    return f"""# Changelog

## [{version}] - 2026-03-12 - "Old Release"

### Changed
- old entry
"""


def _init_repo(tmp_path: Path, *, version: str) -> None:
    _write(tmp_path / "pyproject.toml", _pyproject_text(version))
    _write(tmp_path / "CHANGELOG.md", _changelog_text(version))
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)


# Layer: contract
def test_prepare_core_release_updates_canonical_files_for_minor_release(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.3.18")

    exit_code = main(["--repo-root", str(tmp_path), "--tag", "v0.4.0", "--title", "The Process Cut", "--date", "2026-03-13"])

    assert exit_code == 0
    assert 'version = "0.4.0"' in _read(tmp_path / "pyproject.toml")
    changelog_text = _read(tmp_path / "CHANGELOG.md")
    assert '## [0.4.0] - 2026-03-13 - "The Process Cut"' in changelog_text
    assert changelog_text.index("## [0.4.0]") < changelog_text.index("## [0.3.18]")
    proof_text = _read(tmp_path / "docs" / "releases" / "0.4.0" / "PROOF_REPORT.md")
    assert "Git tag: `v0.4.0`" in proof_text


# Layer: contract
def test_prepare_core_release_commit_and_tag_rejects_placeholder_minor_release_content(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.3.18")

    prepare_exit = main(["--repo-root", str(tmp_path), "--tag", "v0.4.0", "--date", "2026-03-13"])
    assert prepare_exit == 0

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--tag",
            "v0.4.0",
            "--date",
            "2026-03-13",
            "--commit-and-tag",
        ]
    )

    assert exit_code == 1
    tag_exists = subprocess.run(
        ["git", "rev-parse", "--verify", "refs/tags/v0.4.0"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).returncode
    assert tag_exists != 0


# Layer: integration
def test_prepare_core_release_commit_and_tag_creates_annotated_tag_when_release_files_are_ready(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.3.18")

    prepare_exit = main(["--repo-root", str(tmp_path), "--tag", "v0.4.0", "--title", "The Process Cut", "--date", "2026-03-13"])
    assert prepare_exit == 0

    _replace(tmp_path / "CHANGELOG.md", "- Pending release notes.", "- Release process authority is now locked.")
    _write(
        tmp_path / "docs" / "releases" / "0.4.0" / "PROOF_REPORT.md",
        """# Release `0.4.0` Proof Report

Date: `2026-03-13`
Owner: `Orket Core`
Git tag: `v0.4.0`
Completed major project: `docs/projects/archive/techdebt/RP03122026/Closeout.md`
Release policy authority: [docs/specs/CORE_RELEASE_VERSIONING_POLICY.md](docs/specs/CORE_RELEASE_VERSIONING_POLICY.md)
Release gate checklist: [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)

## Summary of Change

Release process authority and enforcement were aligned for the core engine.

## Stability Statement

Core release/versioning authority is stable for the supported surface.

## Compatibility Classification

- `compatibility_status`: `preserved`
- `affected_audience`: `all`
- `migration_requirement`: `none`

## Required Operator or Extension-Author Action

None.

## Proof Record Index

| Surface | Surface Type | Proof Mode | Proof Result | Reason | Evidence |
| --- | --- | --- | --- | --- | --- |
| `release-policy` | `workflow_path` | `structural` | `success` | `none` | `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md` |

## Detailed Proof Records

### `release-policy`

- `surface_type`: `workflow_path`
- `proof_mode`: `structural`
- `proof_result`: `success`
- `reason`: `none`
- `evidence`: `docs/specs/CORE_RELEASE_VERSIONING_POLICY.md`
- `notes`: `Template placeholders removed for release readiness.`
""",
    )

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--tag",
            "v0.4.0",
            "--date",
            "2026-03-13",
            "--commit-and-tag",
        ]
    )

    assert exit_code == 0
    tag_type = subprocess.run(
        ["git", "cat-file", "-t", "refs/tags/v0.4.0"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert tag_type == "tag"
    head_message = subprocess.run(
        ["git", "log", "-1", "--pretty=%s"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    assert head_message == "Prepare core release v0.4.0"


# Layer: integration
def test_prepare_core_release_commit_and_tag_rejects_unrelated_dirty_paths(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.3.18")
    _write(tmp_path / "notes.txt", "unrelated draft")

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path),
            "--tag",
            "v0.4.0",
            "--date",
            "2026-03-13",
            "--commit-and-tag",
        ]
    )

    assert exit_code == 1
    assert not (tmp_path / "docs" / "releases" / "0.4.0" / "PROOF_REPORT.md").exists()
