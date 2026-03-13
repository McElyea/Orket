from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.governance.check_core_release_policy import main


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _pyproject_text(version: str) -> str:
    return f"""[project]
name = "orket"
version = "{version}"
"""


def _changelog_text(version: str) -> str:
    return f"""# Changelog

## [{version}] - 2026-03-12

### Changed
- test entry
"""


def _init_repo(tmp_path: Path, *, version: str, proof_report: bool = False) -> None:
    _write(tmp_path / "pyproject.toml", _pyproject_text(version))
    _write(tmp_path / "CHANGELOG.md", _changelog_text(version))
    _write(tmp_path / "src.py", "VALUE = 1\n")
    _write(tmp_path / "README.md", "# Test Repo\n")
    if proof_report:
        _write(tmp_path / "docs" / "releases" / version / "PROOF_REPORT.md", "# Proof Report\n")

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp_path, check=True, capture_output=True)


def _head_sha(tmp_path: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _commit_all(tmp_path: Path, message: str) -> str:
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=tmp_path, check=True, capture_output=True)
    return _head_sha(tmp_path)


def test_check_core_release_policy_passes_for_current_alignment_and_writes_result(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", _pyproject_text("0.3.18"))
    _write(tmp_path / "CHANGELOG.md", _changelog_text("0.3.18"))
    out_path = tmp_path / "out.json"

    exit_code = main(["--repo-root", str(tmp_path), "--out", str(out_path)])

    assert exit_code == 0
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["assertions"][0]["id"] == "head_version_matches_changelog"
    assert "diff_ledger" in payload


def test_check_core_release_policy_fails_on_head_changelog_drift(tmp_path: Path) -> None:
    _write(tmp_path / "pyproject.toml", _pyproject_text("0.3.18"))
    _write(tmp_path / "CHANGELOG.md", _changelog_text("0.3.17"))

    exit_code = main(["--repo-root", str(tmp_path)])

    assert exit_code == 1


def test_check_core_release_policy_skips_pre_transition_non_exempt_commit_without_bump(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.3.18")
    base_sha = _head_sha(tmp_path)
    _write(tmp_path / "src.py", "VALUE = 2\n")
    head_sha = _commit_all(tmp_path, "code change without bump")

    exit_code = main(["--repo-root", str(tmp_path), "--base-rev", base_sha, "--head-rev", head_sha])

    assert exit_code == 0


def test_check_core_release_policy_fails_on_post_transition_non_exempt_commit_without_bump(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.4.0")
    base_sha = _head_sha(tmp_path)
    _write(tmp_path / "src.py", "VALUE = 2\n")
    head_sha = _commit_all(tmp_path, "code change without bump")

    exit_code = main(["--repo-root", str(tmp_path), "--base-rev", base_sha, "--head-rev", head_sha])

    assert exit_code == 1


def test_check_core_release_policy_allows_post_transition_docs_only_commit_without_bump(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.4.0")
    base_sha = _head_sha(tmp_path)
    _write(tmp_path / "README.md", "# Updated Docs\n")
    head_sha = _commit_all(tmp_path, "docs only")

    exit_code = main(["--repo-root", str(tmp_path), "--base-rev", base_sha, "--head-rev", head_sha])

    assert exit_code == 0


def test_check_core_release_policy_validates_annotated_minor_tag_and_proof_report(tmp_path: Path) -> None:
    _init_repo(tmp_path, version="0.4.0", proof_report=True)
    subprocess.run(["git", "tag", "-a", "v0.4.0", "-m", "release"], cwd=tmp_path, check=True, capture_output=True)

    exit_code = main(["--repo-root", str(tmp_path), "--tag", "v0.4.0"])

    assert exit_code == 0
