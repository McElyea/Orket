from __future__ import annotations

import json
import subprocess
from pathlib import Path

from orket.application.review.run_service import ReviewRunService, _resolve_token
from orket.application.review.models import ReviewSnapshot, SnapshotBounds


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


def test_review_run_diff_writes_bundle_and_replay(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.txt").write_text("one\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    (repo / "a.txt").write_text("one\ntwo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace)
    run = service.run_diff(
        repo_root=repo,
        base_ref=base,
        head_ref=head,
        bounds=SnapshotBounds(),
    )
    run_dir = Path(run.artifact_dir)
    assert (run_dir / "snapshot.json").is_file()
    assert (run_dir / "policy_resolved.json").is_file()
    assert (run_dir / "deterministic_decision.json").is_file()
    assert (run_dir / "run_manifest.json").is_file()

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    policy = json.loads((run_dir / "policy_resolved.json").read_text(encoding="utf-8"))
    replay = service.replay(
        repo_root=repo,
        snapshot=ReviewSnapshot.from_dict(snapshot),
        resolved_policy_payload={k: v for k, v in policy.items() if k != "policy_digest"},
    )
    replay_dir = Path(replay.artifact_dir)
    first_decision = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    replay_decision = json.loads((replay_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    assert first_decision["decision"] == replay_decision["decision"]
    assert first_decision["findings"] == replay_decision["findings"]


def test_token_resolution_precedence(monkeypatch) -> None:
    monkeypatch.setenv("ORKET_GITEA_TOKEN", "canon")
    monkeypatch.setenv("GITEA_TOKEN", "alias")
    token, source = _resolve_token("cli")
    assert token == "cli"
    assert source == "token_flag"

    token, source = _resolve_token("")
    assert token == "canon"
    assert source == "token_env"

    monkeypatch.delenv("ORKET_GITEA_TOKEN")
    token, source = _resolve_token("")
    assert token == "alias"
    assert source == "token_env"
