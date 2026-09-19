from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from scripts.common.git_inventory import GitInventoryError, git_list_files
from scripts.governance.export_review_packet import export_project_review_packet


def _git(repo: Path, *args: str):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, timeout=20)


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    return repo


def _cli(repo: Path, *args: str):
    return subprocess.run(
        [sys.executable, "-m", "scripts.governance.export_review_packet", str(repo), *args],
        cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True, timeout=20, check=False,
    )


@pytest.mark.integration
# Layer: integration
def test_review_packet_respects_gitignored_files(tmp_path: Path) -> None:
    """Layer: integration. Real Git and packet output exclude ignored local configuration."""
    repo = _repo(tmp_path)
    (repo / ".gitignore").write_text(".claude/\n", encoding="utf-8")
    (repo / "visible.py").write_text("print('visible')\n", encoding="utf-8")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "settings.local.json").write_text('{"secret": true}\n', encoding="utf-8")

    assert export_project_review_packet(root_dir=str(repo), output_file="dump.txt")

    dump_text = (repo / "dump.txt").read_text(encoding="utf-8")
    assert "visible.py" in dump_text
    assert ".claude/settings.local.json" not in dump_text


@pytest.mark.integration
# Layer: integration
def test_inventory_preserves_tracked_and_untracked_names_and_excludes_deleted_files(tmp_path: Path):
    """Layer: integration. Real Git handles spaces/Unicode, modified tracked files and missing paths."""
    repo = _repo(tmp_path)
    tracked = repo / "tracked name.py"
    deleted = repo / "deleted.py"
    tracked.write_text("original", encoding="utf-8")
    deleted.write_text("removed", encoding="utf-8")
    _git(repo, "add", ".")
    deleted.unlink()
    tracked.write_text("modified", encoding="utf-8")
    untracked = repo / "unicode-\N{LATIN SMALL LETTER E WITH ACUTE}.py"
    untracked.write_text("untracked", encoding="utf-8")
    assert git_list_files(repo) == sorted([tracked, untracked], key=lambda path: path.name)


@pytest.mark.integration
# Layer: integration
def test_inventory_and_export_work_in_a_real_git_worktree(tmp_path: Path):
    """Layer: integration. A .git indirection file provides the same inventory without a local exporter."""
    repo = _repo(tmp_path)
    (repo / "visible.py").write_text("retained source", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-m", "fixture")
    worktree = tmp_path / "worktree"
    _git(repo, "worktree", "add", "--detach", str(worktree))
    try:
        assert (worktree / ".git").is_file()
        assert git_list_files(worktree) == [worktree / "visible.py"]
        result = _cli(worktree)
        assert result.returncode == 0, result.stderr
        packet = worktree / "Agents/review/project_review_packet.txt"
        assert "retained source" in packet.read_text(encoding="utf-8")
    finally:
        assert worktree.resolve().is_relative_to(tmp_path.resolve()) and worktree.resolve() != tmp_path.resolve()
        _git(repo, "worktree", "remove", "--force", str(worktree))


@pytest.mark.integration
# Layer: integration
def test_git_failure_is_not_an_empty_inventory_or_filesystem_fallback(tmp_path: Path, monkeypatch):
    """Layer: integration. Failed discovery is visible and preserves an existing output artifact."""
    # An in-repository --basetemp must not discover the enclosing checkout.
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent.resolve()))
    discovery = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"],
                               capture_output=True, text=True, timeout=20, check=False)
    assert discovery.returncode != 0 and "not a git repository" in discovery.stderr.lower()
    output = tmp_path / "packet.txt"
    output.write_text("preserve existing packet", encoding="utf-8")
    with pytest.raises(GitInventoryError):
        git_list_files(tmp_path)
    result = _cli(tmp_path, "--output", str(output))
    assert result.returncode == 1 and "Review packet failed" in result.stderr
    assert output.read_text(encoding="utf-8") == "preserve existing packet"


@pytest.mark.integration
@pytest.mark.parametrize("limit_args", [("--max-file-size", "10"), ("--max-total-chars", "300")])
# Layer: integration
def test_cli_reports_partial_output_when_a_bound_omits_eligible_content(tmp_path: Path, limit_args):
    """Layer: integration. Byte/character caps produce a disclosed partial packet and nonzero status."""
    repo = _repo(tmp_path)
    (repo / "large.py").write_text("x" * 1000, encoding="utf-8")
    output = repo / "packet.txt"
    result = _cli(repo, "--output", str(output), *limit_args)
    assert result.returncode == 2, result.stderr
    packet = output.read_text(encoding="utf-8")
    assert "Result: partial; eligible content omitted" in packet
    if limit_args[0] == "--max-total-chars":
        assert len(packet) <= 300


@pytest.mark.integration
# Layer: integration
def test_tracked_local_environment_file_is_excluded_from_review_copy(tmp_path: Path):
    """Layer: integration. A Git-visible local environment file is filtered before reading it into a packet."""
    repo = _repo(tmp_path)
    (repo / ".env.local").write_text("PRIVATE_FIXTURE=do-not-export", encoding="utf-8")
    (repo / "visible.py").write_text("public source", encoding="utf-8")
    _git(repo, "add", ".")
    output = repo / "packet.txt"
    result = _cli(repo, "--output", str(output))
    assert result.returncode == 0, result.stderr
    packet = output.read_text(encoding="utf-8")
    assert "public source" in packet and "do-not-export" not in packet


@pytest.mark.integration
# Layer: integration
def test_invalid_utf8_refuses_to_replace_an_existing_packet(tmp_path: Path):
    """Layer: integration. A source decoding failure cannot be silently rendered as a complete review copy."""
    repo = _repo(tmp_path)
    (repo / "invalid.py").write_bytes(b"\xff")
    output = repo / "packet.txt"
    output.write_text("previous packet", encoding="utf-8")
    result = _cli(repo, "--output", str(output))
    assert result.returncode == 1 and "Review packet failed" in result.stderr
    assert output.read_text(encoding="utf-8") == "previous packet"
