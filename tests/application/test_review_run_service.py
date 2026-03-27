from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import orket.application.review.run_service as run_service_module
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.review.run_service import ReviewRunService, _resolve_token
from orket.application.review.models import ChangedFile, ReviewSnapshot, SnapshotBounds, TruncationReport
from orket.capabilities.sync_bridge import run_coro_sync
from orket.core.domain import AttemptState, RunState


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


def test_review_run_diff_writes_bundle_and_replay(tmp_path: Path) -> None:
    """Layer: integration. Verifies review runs persist artifact bundles and first-class control-plane execution truth."""
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
    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=control_plane_db)
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
    assert run.manifest["execution_state_authority"] == "control_plane_records"
    assert run.manifest["lane_outputs_execution_state_authoritative"] is False
    assert run.manifest["control_plane_run_id"] == run.run_id
    assert run.manifest["control_plane_attempt_id"].startswith(f"{run.run_id}:attempt:")
    assert run.manifest["control_plane_step_id"].startswith(f"{run.run_id}:step:")
    assert run.control_plane is not None
    assert run.control_plane["run_state"] == "completed"
    assert run.control_plane["attempt_state"] == "attempt_completed"
    assert run.control_plane["step_kind"] == "review_run_start"

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    record_repo = AsyncControlPlaneRecordRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run.run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED
    persisted_attempt = run_coro_sync(
        execution_repo.get_attempt_record(attempt_id=run.manifest["control_plane_attempt_id"])
    )
    assert persisted_attempt is not None
    assert persisted_attempt.attempt_state is AttemptState.COMPLETED
    persisted_step = run_coro_sync(execution_repo.get_step_record(step_id=run.manifest["control_plane_step_id"]))
    assert persisted_step is not None
    assert persisted_step.step_kind == "review_run_start"
    policy_snapshot = run_coro_sync(
        record_repo.get_resolved_policy_snapshot(snapshot_id=persisted_run.policy_snapshot_id)
    )
    configuration_snapshot = run_coro_sync(
        record_repo.get_resolved_configuration_snapshot(snapshot_id=persisted_run.configuration_snapshot_id)
    )
    assert policy_snapshot is not None
    assert configuration_snapshot is not None

    snapshot = json.loads((run_dir / "snapshot.json").read_text(encoding="utf-8"))
    policy = json.loads((run_dir / "policy_resolved.json").read_text(encoding="utf-8"))
    replay = service.replay(
        repo_root=repo,
        snapshot=ReviewSnapshot.from_dict(snapshot),
        resolved_policy_payload={k: v for k, v in policy.items() if k != "policy_digest"},
    )
    assert replay.control_plane is not None
    assert replay.control_plane["run_state"] == "completed"
    replay_dir = Path(replay.artifact_dir)
    first_decision = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    replay_decision = json.loads((replay_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    assert first_decision["decision"] == replay_decision["decision"]
    assert first_decision["findings"] == replay_decision["findings"]


def test_token_resolution_precedence(monkeypatch) -> None:
    """Layer: unit. Verifies CLI and environment token precedence remains explicit and stable."""
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


def test_run_diff_defaults_to_code_only_scope(tmp_path: Path) -> None:
    """Layer: integration. Verifies diff reviews honor the default code-only snapshot policy."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "app").mkdir(parents=True, exist_ok=True)
    (repo / "app" / "x.py").write_text("print('x')\n", encoding="utf-8")
    (repo / "README.md").write_text("base\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    (repo / "app" / "x.py").write_text("print('y')\n", encoding="utf-8")
    (repo / "README.md").write_text("changed readme\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=tmp_path / "control_plane.sqlite3")
    run = service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())
    snapshot = json.loads((Path(run.artifact_dir) / "snapshot.json").read_text(encoding="utf-8"))
    changed_paths = [row["path"] for row in snapshot.get("changed_files", [])]
    assert "README.md" not in changed_paths
    assert "app/x.py" in changed_paths


def test_run_pr_fetches_snapshot_once_in_code_only_mode(monkeypatch, tmp_path: Path) -> None:
    """Layer: contract. Verifies code-only PR reviews filter the fetched snapshot locally instead of reloading it."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "remote", "add", "origin", "https://example.test/org/repo.git")
    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=tmp_path / "control_plane.sqlite3")
    calls: list[set[str] | None] = []
    captured: dict[str, list[str]] = {}

    snapshot = ReviewSnapshot(
        source="pr",
        repo={"remote": "https://example.test", "repo_id": "org/repo"},
        base_ref="base",
        head_ref="head",
        bounds=SnapshotBounds(),
        truncation=TruncationReport(
            files_truncated=0,
            diff_bytes_original=0,
            diff_bytes_kept=0,
            diff_truncated=False,
            blob_bytes_original=0,
            blob_bytes_kept=0,
            blob_truncated=False,
            notes=[],
        ),
        changed_files=[
            ChangedFile(path="app/main.py", status="modified", additions=1, deletions=0),
            ChangedFile(path="README.md", status="modified", additions=1, deletions=0),
        ],
        diff_unified=(
            "diff --git a/app/main.py b/app/main.py\n"
            "--- a/app/main.py\n"
            "+++ b/app/main.py\n"
            "@@ -1 +1 @@\n"
            "-print('old')\n"
            "+print('new')\n"
            "diff --git a/README.md b/README.md\n"
            "--- a/README.md\n"
            "+++ b/README.md\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        ),
        context_blobs=[],
        metadata={"title": "PR"},
    )
    snapshot.compute_snapshot_digest()

    monkeypatch.setattr(
        run_service_module,
        "resolve_review_policy",
        lambda **_kwargs: SimpleNamespace(
            payload={"input_scope": {"mode": "code_only", "code_extensions": [".py"]}},
            policy_digest="policy",
        ),
    )

    def _fake_load_from_pr(**kwargs):  # type: ignore[no-untyped-def]
        calls.append(kwargs.get("include_paths"))
        return snapshot

    def _fake_execute(self, *, snapshot, **_kwargs):  # type: ignore[no-untyped-def]
        captured["paths"] = [row.path for row in snapshot.changed_files]
        return "ok"

    monkeypatch.setattr(run_service_module, "load_from_pr", _fake_load_from_pr)
    monkeypatch.setattr(ReviewRunService, "_execute", _fake_execute)

    result = service.run_pr(
        remote="https://example.test",
        repo="org/repo",
        pr=7,
        repo_root=repo,
        bounds=SnapshotBounds(),
    )

    assert result == "ok"
    assert calls == [None]
    assert captured["paths"] == ["app/main.py"]


def test_review_run_failure_closes_control_plane_run_failed(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies review-run execution errors close the durable control-plane run truthfully."""
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

    run_id = "01TESTREVIEWRUNFAIL0000000000"
    monkeypatch.setattr(run_service_module, "_ulid", lambda: run_id)

    def _boom(**_kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("lane failed")

    monkeypatch.setattr(run_service_module, "run_deterministic_lane", _boom)

    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=tmp_path / "workspace" / "default", control_plane_db_path=control_plane_db)

    with pytest.raises(RuntimeError, match="lane failed"):
        service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.FAILED_TERMINAL
    persisted_attempt = run_coro_sync(
        execution_repo.get_attempt_record(attempt_id=f"{run_id}:attempt:0001")
    )
    assert persisted_attempt is not None
    assert persisted_attempt.attempt_state is AttemptState.FAILED
    assert persisted_attempt.failure_class == "review_run_RuntimeError"
