from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orket.interfaces.orket_bundle_cli import main


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


def test_review_diff_cli_emits_bundle(tmp_path: Path, capsys) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    (repo / "a.txt").write_text("a\nb\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "next")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    workspace = tmp_path / "workspace" / "default"
    code = main(
        [
            "review",
            "diff",
            "--repo-root",
            str(repo),
            "--base",
            base,
            "--head",
            head,
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["ok"] is True
    assert Path(payload["artifact_dir"]).is_dir()


def test_review_replay_cli_requires_inputs(tmp_path: Path, capsys) -> None:
    code = main(["review", "replay", "--workspace", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["ok"] is False


def test_review_cli_rejects_conflicting_scope_flags(tmp_path: Path, capsys) -> None:
    code = main(
        [
            "review",
            "files",
            "--repo-root",
            str(tmp_path),
            "--ref",
            "HEAD",
            "--paths",
            "app/a.py",
            "--code-only",
            "--all-files",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["ok"] is False
