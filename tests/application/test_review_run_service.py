from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import orket.application.review.run_service as run_service_module
from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.application.review.control_plane_projection import REVIEW_CONTROL_PLANE_PROJECTION_SOURCE
from orket.application.review.models import (
    ChangedFile,
    DeterministicReviewDecisionPayload,
    ModelAssistedCritiquePayload,
    ReviewRunManifest,
    ReviewRunResult,
    ReviewSnapshot,
    SnapshotBounds,
    TruncationReport,
)
from orket.application.review.run_service import ReviewRunService, _resolve_token
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
    assert run.control_plane["projection_source"] == REVIEW_CONTROL_PLANE_PROJECTION_SOURCE
    assert run.control_plane["projection_only"] is True
    assert run.control_plane["run_state"] == "completed"
    assert run.control_plane["attempt_state"] == "attempt_completed"
    assert run.control_plane["step_kind"] == "review_run_start"
    deterministic_payload = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    assert deterministic_payload["execution_state_authority"] == "control_plane_records"
    assert deterministic_payload["lane_output_execution_state_authoritative"] is False
    assert deterministic_payload["control_plane_run_id"] == run.run_id
    assert deterministic_payload["control_plane_attempt_id"] == run.manifest["control_plane_attempt_id"]
    assert deterministic_payload["control_plane_step_id"] == run.manifest["control_plane_step_id"]

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
    assert replay.control_plane["projection_source"] == REVIEW_CONTROL_PLANE_PROJECTION_SOURCE
    assert replay.control_plane["projection_only"] is True
    assert replay.control_plane["run_state"] == "completed"
    replay_dir = Path(replay.artifact_dir)
    first_decision = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    replay_decision = json.loads((replay_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    assert first_decision["decision"] == replay_decision["decision"]
    assert first_decision["findings"] == replay_decision["findings"]


def test_review_run_model_assisted_artifact_marks_execution_state_non_authoritative(tmp_path: Path) -> None:
    """Layer: integration. Verifies advisory review-lane artifacts point back to durable control-plane execution truth."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "a.py").write_text("print('one')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()
    (repo / "a.py").write_text("print('two')\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "change")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True).stdout.decode().strip()

    workspace = tmp_path / "workspace" / "default"
    service = ReviewRunService(workspace=workspace, control_plane_db_path=tmp_path / "control_plane.sqlite3")
    run = service.run_diff(
        repo_root=repo,
        base_ref=base,
        head_ref=head,
        bounds=SnapshotBounds(),
        cli_policy_overrides={"model_assisted": {"enabled": True, "model_id": "test-model"}},
        model_provider=lambda _request: {
            "summary": ["Advisory only."],
            "high_risk_issues": [],
            "missing_tests": [],
            "questions_for_author": [],
            "nits": [],
            "refs": [],
        },
    )

    critique_payload = json.loads((Path(run.artifact_dir) / "model_assisted_critique.json").read_text(encoding="utf-8"))
    assert critique_payload["execution_state_authority"] == "control_plane_records"
    assert critique_payload["lane_output_execution_state_authoritative"] is False
    assert critique_payload["control_plane_run_id"] == run.run_id
    assert critique_payload["control_plane_attempt_id"] == run.manifest["control_plane_attempt_id"]
    assert critique_payload["control_plane_step_id"] == run.manifest["control_plane_step_id"]
    assert critique_payload["summary"] == ["Advisory only."]


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
    monkeypatch.setattr(run_service_module, "_generate_ulid", lambda: run_id)

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


def test_review_run_service_rejects_control_plane_summary_identifier_drift(tmp_path: Path, monkeypatch) -> None:
    """Layer: integration. Verifies review-run execution fails closed if projected control-plane ids drift."""
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

    run_id = "01TESTREVIEWRUNDRIFT0000000000"
    monkeypatch.setattr(run_service_module, "_generate_ulid", lambda: run_id)

    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=tmp_path / "workspace" / "default", control_plane_db_path=control_plane_db)

    async def _drifted_summary(*, run_id: str) -> dict[str, object]:
        return {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": run_id,
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_id": f"{run_id}:attempt:9999",
            "attempt_state": "attempt_completed",
            "attempt_ordinal": 1,
            "policy_snapshot_id": f"review-run-policy:{run_id}",
            "configuration_snapshot_id": f"review-run-config:{run_id}",
            "step_id": f"{run_id}:step:start",
            "step_kind": "review_run_start",
        }

    monkeypatch.setattr(service.review_control_plane_service, "read_execution_summary", _drifted_summary)

    with pytest.raises(ValueError, match="review_control_plane_attempt_id_mismatch"):
        service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED


@pytest.mark.parametrize(
    ("summary_overrides", "expected_error"),
    [
        ({"workload_id": ""}, "review_control_plane_workload_id_required"),
        ({"attempt_ordinal": None}, "review_control_plane_attempt_ordinal_required"),
    ],
)
def test_review_run_service_rejects_incomplete_control_plane_lifecycle_projection(
    tmp_path: Path,
    monkeypatch,
    summary_overrides: dict[str, object],
    expected_error: str,
) -> None:
    """Layer: integration. Verifies review-run execution fails closed if projected lifecycle state is incomplete."""
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

    run_id = "01TESTREVIEWRUNSTATE0000000000"
    monkeypatch.setattr(run_service_module, "_generate_ulid", lambda: run_id)

    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=tmp_path / "workspace" / "default", control_plane_db_path=control_plane_db)

    async def _incomplete_summary(*, run_id: str) -> dict[str, object]:
        summary = {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": run_id,
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_id": f"{run_id}:attempt:0001",
            "attempt_state": "attempt_completed",
            "attempt_ordinal": 1,
            "policy_snapshot_id": f"review-run-policy:{run_id}",
            "configuration_snapshot_id": f"review-run-config:{run_id}",
            "step_id": f"{run_id}:step:start",
            "step_kind": "review_run_start",
        }
        summary.update(summary_overrides)
        return summary

    monkeypatch.setattr(service.review_control_plane_service, "read_execution_summary", _incomplete_summary)

    with pytest.raises(ValueError, match=expected_error):
        service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED


@pytest.mark.parametrize(
    ("summary_overrides", "expected_error"),
    [
        (
            {
                "run_id": "",
                "attempt_id": "01TESTREVIEWRUNHIER0000000000:attempt:0001",
                "step_id": "01TESTREVIEWRUNHIER0000000000:step:start",
            },
            "review_control_plane_run_id_required",
        ),
        (
            {
                "attempt_id": "",
                "step_id": "01TESTREVIEWRUNHIER0000000000:step:start",
            },
            "review_control_plane_attempt_id_required",
        ),
    ],
)
def test_review_run_service_rejects_orphaned_control_plane_identifier_hierarchy(
    tmp_path: Path,
    monkeypatch,
    summary_overrides: dict[str, object],
    expected_error: str,
) -> None:
    """Layer: integration. Verifies review-run execution fails closed if lower-level projected ids outlive their parent ids."""
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

    run_id = "01TESTREVIEWRUNHIER0000000000"
    monkeypatch.setattr(run_service_module, "_generate_ulid", lambda: run_id)

    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=tmp_path / "workspace" / "default", control_plane_db_path=control_plane_db)

    async def _orphaned_summary(*, run_id: str) -> dict[str, object]:
        summary = {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": run_id,
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_id": f"{run_id}:attempt:0001",
            "attempt_state": "attempt_completed",
            "attempt_ordinal": 1,
            "policy_snapshot_id": f"review-run-policy:{run_id}",
            "configuration_snapshot_id": f"review-run-config:{run_id}",
            "step_id": f"{run_id}:step:start",
            "step_kind": "review_run_start",
        }
        summary.update(summary_overrides)
        return summary

    monkeypatch.setattr(service.review_control_plane_service, "read_execution_summary", _orphaned_summary)

    with pytest.raises(ValueError, match=expected_error):
        service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED


@pytest.mark.parametrize(
    ("summary_overrides", "expected_error"),
    [
        (
            {
                "attempt_id": "",
                "attempt_state": "attempt_completed",
                "attempt_ordinal": "",
                "step_id": "",
                "step_kind": "",
            },
            "review_control_plane_attempt_id_required",
        ),
        (
            {
                "attempt_id": "",
                "attempt_state": "",
                "attempt_ordinal": 1,
                "step_id": "",
                "step_kind": "",
            },
            "review_control_plane_attempt_id_required",
        ),
        (
            {
                "step_id": "",
                "step_kind": "review_run_start",
            },
            "review_control_plane_step_id_required",
        ),
    ],
)
def test_review_run_service_rejects_orphaned_control_plane_projection_metadata(
    tmp_path: Path,
    monkeypatch,
    summary_overrides: dict[str, object],
    expected_error: str,
) -> None:
    """Layer: integration. Verifies review-run execution fails closed if attempt or step metadata survives after its projected id drops."""
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

    run_id = "01TESTREVIEWRUNMETA0000000000"
    monkeypatch.setattr(run_service_module, "_generate_ulid", lambda: run_id)

    control_plane_db = tmp_path / "control_plane.sqlite3"
    service = ReviewRunService(workspace=tmp_path / "workspace" / "default", control_plane_db_path=control_plane_db)

    async def _orphaned_metadata_summary(*, run_id: str) -> dict[str, object]:
        summary = {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": run_id,
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_id": f"{run_id}:attempt:0001",
            "attempt_state": "attempt_completed",
            "attempt_ordinal": 1,
            "policy_snapshot_id": f"review-run-policy:{run_id}",
            "configuration_snapshot_id": f"review-run-config:{run_id}",
            "step_id": f"{run_id}:step:start",
            "step_kind": "review_run_start",
        }
        summary.update(summary_overrides)
        return summary

    monkeypatch.setattr(service.review_control_plane_service, "read_execution_summary", _orphaned_metadata_summary)

    with pytest.raises(ValueError, match=expected_error):
        service.run_diff(repo_root=repo, base_ref=base, head_ref=head, bounds=SnapshotBounds())

    execution_repo = AsyncControlPlaneExecutionRepository(control_plane_db)
    persisted_run = run_coro_sync(execution_repo.get_run_record(run_id=run_id))
    assert persisted_run is not None
    assert persisted_run.lifecycle_state is RunState.COMPLETED


def test_review_run_result_rejects_malformed_control_plane_projection() -> None:
    """Layer: contract. Verifies review result JSON fail-closes if control-plane projection framing drifts."""
    result = ReviewRunResult(
        ok=True,
        run_id="run-1",
        artifact_dir="workspace/default/review_runs/run-1",
        snapshot_digest="sha256:snapshot",
        policy_digest="sha256:policy",
        deterministic_decision="pass",
        deterministic_findings=0,
        model_assisted_enabled=False,
        manifest={
            "run_id": "run-1",
            "execution_state_authority": "control_plane_records",
            "lane_outputs_execution_state_authoritative": False,
        },
        control_plane={
            "projection_source": "wrong_source",
            "projection_only": True,
            "run_id": "run-1",
            "run_state": "completed",
        },
    )

    with pytest.raises(ValueError, match="review_control_plane_projection_source_invalid"):
        result.to_dict()


@pytest.mark.parametrize(
    ("factory", "expected_error"),
    [
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                execution_state_authority="wrong_source",
            ),
            "deterministic_review_decision_execution_state_authority_invalid",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                lane_output_execution_state_authoritative=True,
            ),
            "model_assisted_critique_execution_state_authoritative_invalid",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="run-1",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
                lane_outputs_execution_state_authoritative=True,
            ),
            "review_run_manifest_execution_state_authoritative_invalid",
        ),
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="",
            ),
            "deterministic_review_decision_run_id_required",
        ),
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="",
                control_plane_attempt_id="run-1:attempt:0001",
                control_plane_step_id="run-1:step:start",
            ),
            "deterministic_review_decision_control_plane_run_id_required",
        ),
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-2",
            ),
            "deterministic_review_decision_control_plane_run_id_mismatch",
        ),
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-2:attempt:0001",
            ),
            "deterministic_review_decision_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            lambda: DeterministicReviewDecisionPayload(
                decision="pass",
                findings=[],
                executed_checks=[],
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-1:attempt:0001",
                control_plane_step_id="run-2:step:start",
            ),
            "deterministic_review_decision_control_plane_step_id_run_lineage_mismatch",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="",
            ),
            "model_assisted_critique_run_id_required",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-1",
                control_plane_attempt_id="",
                control_plane_step_id="run-1:step:start",
            ),
            "model_assisted_critique_control_plane_attempt_id_required",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-2",
            ),
            "model_assisted_critique_control_plane_run_id_mismatch",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-2:attempt:0001",
            ),
            "model_assisted_critique_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            lambda: ModelAssistedCritiquePayload(
                summary=[],
                high_risk_issues=[],
                missing_tests=[],
                questions_for_author=[],
                nits=[],
                refs=[],
                model_id="test-model",
                prompt_profile="review",
                contract_version="review_critique_v0",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                run_id="run-1",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-1:attempt:0001",
                control_plane_step_id="run-2:step:start",
            ),
            "model_assisted_critique_control_plane_step_id_run_lineage_mismatch",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
            ),
            "review_run_manifest_run_id_required",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="run-1",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
                control_plane_run_id="run-1",
                control_plane_attempt_id="",
                control_plane_step_id="run-1:step:start",
            ),
            "review_run_manifest_control_plane_attempt_id_required",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="run-1",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
                control_plane_run_id="run-2",
            ),
            "review_run_manifest_control_plane_run_id_mismatch",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="run-1",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-2:attempt:0001",
            ),
            "review_run_manifest_control_plane_attempt_id_run_lineage_mismatch",
        ),
        (
            lambda: ReviewRunManifest(
                run_id="run-1",
                snapshot_digest="sha256:snapshot",
                policy_digest="sha256:policy",
                review_run_contract_version="review_run_v0",
                deterministic_lane_version="deterministic_v0",
                bounds={},
                truncation={},
                auth_source="none",
                control_plane_run_id="run-1",
                control_plane_attempt_id="run-1:attempt:0001",
                control_plane_step_id="run-2:step:start",
            ),
            "review_run_manifest_control_plane_step_id_run_lineage_mismatch",
        ),
    ],
)
def test_review_artifact_models_reject_execution_authority_drift(factory, expected_error: str) -> None:
    """Layer: contract. Verifies review artifact surfaces fail closed on execution-authority marker drift."""
    with pytest.raises(ValueError, match=expected_error):
        factory().to_dict()
