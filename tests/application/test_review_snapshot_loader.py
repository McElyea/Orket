from __future__ import annotations

import subprocess
from pathlib import Path

from orket.application.review.models import SnapshotBounds
from orket.application.review.snapshot_loader import load_from_diff, load_from_files


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


def test_snapshot_diff_digest_stable(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "update")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    snapshot_a = load_from_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())
    snapshot_b = load_from_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())
    assert snapshot_a.snapshot_digest == snapshot_b.snapshot_digest
    assert snapshot_a.snapshot_digest.startswith("sha256:")


def test_snapshot_files_truncation_is_explicit(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    content = "x" * 200
    (repo / "a.txt").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    ref = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    snapshot = load_from_files(
        repo_root=repo,
        ref=ref,
        paths=["a.txt"],
        bounds=SnapshotBounds(max_file_bytes=16, max_blob_bytes=16),
    )
    assert snapshot.truncation.blob_truncated is True
    assert snapshot.truncation.blob_bytes_original >= snapshot.truncation.blob_bytes_kept

