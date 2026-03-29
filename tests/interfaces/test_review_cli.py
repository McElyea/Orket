from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from orket.application.review.models import ReviewRunResult
from orket.interfaces.orket_bundle_cli import main


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")


def _create_review_bundle(tmp_path: Path, capsys) -> tuple[Path, dict[str, object]]:
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
    return workspace, payload


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
    assert payload["control_plane"]["projection_source"] == "control_plane_records"
    assert payload["control_plane"]["projection_only"] is True
    assert payload["control_plane"]["run_state"] == "completed"
    assert payload["control_plane"]["attempt_state"] == "attempt_completed"
    assert payload["control_plane"]["run_id"] == payload["run_id"]
    assert payload["control_plane"]["attempt_id"].startswith(f"{payload['run_id']}:attempt:")
    assert payload["control_plane"]["step_id"].startswith(f"{payload['run_id']}:step:")


def test_review_diff_cli_human_output_surfaces_control_plane_refs(tmp_path: Path, capsys) -> None:
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
        ]
    )
    output = capsys.readouterr().out
    assert code == 0
    assert "control-plane: run=completed attempt=attempt_completed step=review_run_start" in output
    assert "control-plane refs: run_id=" in output
    assert "attempt_id=" in output
    assert "step_id=" in output


def test_review_replay_cli_requires_inputs(tmp_path: Path, capsys) -> None:
    code = main(["review", "replay", "--workspace", str(tmp_path), "--json"])
    payload = json.loads(capsys.readouterr().out)
    assert code == 2
    assert payload["ok"] is False


def test_review_replay_cli_run_dir_validates_bundle_and_replays(tmp_path: Path, capsys) -> None:
    """contract: run-dir replay must validate canonical bundle authority markers."""
    workspace, payload = _create_review_bundle(tmp_path, capsys)

    replay_code = main(
        [
            "review",
            "replay",
            "--run-dir",
            str(payload["artifact_dir"]),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_code == 0
    assert replay_payload["ok"] is True
    assert replay_payload["control_plane"]["projection_source"] == "control_plane_records"
    assert replay_payload["control_plane"]["projection_only"] is True


def test_review_replay_cli_run_dir_rejects_drifted_review_manifest(tmp_path: Path, capsys) -> None:
    """contract: run-dir replay must fail closed when canonical bundle authority drifts."""
    workspace, payload = _create_review_bundle(tmp_path, capsys)

    run_dir = Path(str(payload["artifact_dir"]))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["lane_outputs_execution_state_authoritative"] = True
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    replay_code = main(
        [
            "review",
            "replay",
            "--run-dir",
            str(run_dir),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_code == 1
    assert replay_payload["ok"] is False
    assert "review_run_manifest_execution_state_authoritative_invalid" in replay_payload["errors"][0]["message"]


def test_review_replay_cli_snapshot_policy_bundle_paths_validate_bundle_and_replay(tmp_path: Path, capsys) -> None:
    """contract: direct snapshot/policy replay must validate canonical bundle artifacts when present."""
    workspace, payload = _create_review_bundle(tmp_path, capsys)
    run_dir = Path(str(payload["artifact_dir"]))

    replay_code = main(
        [
            "review",
            "replay",
            "--snapshot",
            str(run_dir / "snapshot.json"),
            "--policy",
            str(run_dir / "policy_resolved.json"),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_code == 0
    assert replay_payload["ok"] is True
    assert replay_payload["control_plane"]["projection_source"] == "control_plane_records"
    assert replay_payload["control_plane"]["projection_only"] is True


def test_review_replay_cli_snapshot_policy_bundle_paths_reject_drifted_review_manifest(tmp_path: Path, capsys) -> None:
    """contract: direct snapshot/policy replay must fail closed on canonical bundle authority drift."""
    workspace, payload = _create_review_bundle(tmp_path, capsys)
    run_dir = Path(str(payload["artifact_dir"]))
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    manifest["lane_outputs_execution_state_authoritative"] = True
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    replay_code = main(
        [
            "review",
            "replay",
            "--snapshot",
            str(run_dir / "snapshot.json"),
            "--policy",
            str(run_dir / "policy_resolved.json"),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_code == 1
    assert replay_payload["ok"] is False
    assert "review_run_manifest_execution_state_authoritative_invalid" in replay_payload["errors"][0]["message"]


def test_review_replay_cli_run_dir_rejects_missing_bundle_control_plane_ref(tmp_path: Path, capsys) -> None:
    """contract: run-dir replay must fail closed when canonical lane control-plane refs are missing."""
    workspace, payload = _create_review_bundle(tmp_path, capsys)

    run_dir = Path(str(payload["artifact_dir"]))
    deterministic = json.loads((run_dir / "deterministic_decision.json").read_text(encoding="utf-8"))
    deterministic.pop("control_plane_step_id", None)
    (run_dir / "deterministic_decision.json").write_text(json.dumps(deterministic), encoding="utf-8")

    replay_code = main(
        [
            "review",
            "replay",
            "--run-dir",
            str(run_dir),
            "--workspace",
            str(workspace),
            "--json",
        ]
    )
    replay_payload = json.loads(capsys.readouterr().out)
    assert replay_code == 1
    assert replay_payload["ok"] is False
    assert "deterministic_review_decision_control_plane_step_id_missing" in replay_payload["errors"][0]["message"]


def test_review_diff_cli_returns_structured_error_on_result_manifest_control_plane_drift(tmp_path: Path, capsys, monkeypatch) -> None:
    """contract: diff CLI must surface structured failure when result serialization detects embedded manifest/control-plane drift."""

    def _fake_run_diff(self, **_kwargs):  # type: ignore[no-untyped-def]
        return ReviewRunResult(
            ok=True,
            run_id="run-1",
            artifact_dir=str(tmp_path / "workspace" / "default" / "review_runs" / "run-1"),
            snapshot_digest="sha256:snapshot",
            policy_digest="sha256:policy",
            deterministic_decision="pass",
            deterministic_findings=0,
            model_assisted_enabled=False,
            manifest={
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
            },
            control_plane={
                "projection_source": "control_plane_records",
                "projection_only": True,
                "run_id": "run-1",
                "attempt_id": "run-1:attempt:0001",
                "attempt_ordinal": 1,
                "step_id": "run-1:step:start",
                "run_state": "completed",
                "workload_id": "review.run",
                "workload_version": "v0",
                "attempt_state": "attempt_completed",
                "policy_snapshot_id": "review-run-policy:run-1",
                "configuration_snapshot_id": "review-run-config:run-1",
                "step_kind": "review_run_start",
            },
        )

    monkeypatch.setattr("orket.interfaces.orket_bundle_cli.ReviewRunService.run_diff", _fake_run_diff)

    code = main(
        [
            "review",
            "diff",
            "--repo-root",
            str(tmp_path),
            "--base",
            "base",
            "--head",
            "head",
            "--workspace",
            str(tmp_path / "workspace" / "default"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_REVIEW_RUN_FAILED"
    assert "review_run_manifest_control_plane_step_id_missing" in payload["errors"][0]["message"]


def test_review_diff_cli_returns_structured_error_on_result_manifest_missing_run_id(tmp_path: Path, capsys, monkeypatch) -> None:
    """contract: diff CLI must surface structured failure when result serialization detects missing manifest run identity."""

    def _fake_run_diff(self, **_kwargs):  # type: ignore[no-untyped-def]
        return ReviewRunResult(
            ok=True,
            run_id="run-1",
            artifact_dir=str(tmp_path / "workspace" / "default" / "review_runs" / "run-1"),
            snapshot_digest="sha256:snapshot",
            policy_digest="sha256:policy",
            deterministic_decision="pass",
            deterministic_findings=0,
            model_assisted_enabled=False,
            manifest={
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
            },
        )

    monkeypatch.setattr("orket.interfaces.orket_bundle_cli.ReviewRunService.run_diff", _fake_run_diff)

    code = main(
        [
            "review",
            "diff",
            "--repo-root",
            str(tmp_path),
            "--base",
            "base",
            "--head",
            "head",
            "--workspace",
            str(tmp_path / "workspace" / "default"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_REVIEW_RUN_FAILED"
    assert "review_run_manifest_run_id_required" in payload["errors"][0]["message"]


@pytest.mark.parametrize(
    ("control_plane_overrides", "expected_error"),
    [
        (
            {
                "attempt_id": "",
                "attempt_ordinal": 1,
                "step_id": "run-1:step:start",
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
def test_review_diff_cli_returns_structured_error_on_orphaned_control_plane_projection(
    tmp_path: Path,
    capsys,
    monkeypatch,
    control_plane_overrides: dict[str, object],
    expected_error: str,
) -> None:
    """contract: diff CLI must surface structured failure when result serialization detects orphaned projected ids or metadata."""

    def _fake_run_diff(self, **_kwargs):  # type: ignore[no-untyped-def]
        control_plane = {
            "projection_source": "control_plane_records",
            "projection_only": True,
            "run_id": "run-1",
            "attempt_id": "run-1:attempt:0001",
            "attempt_ordinal": 1,
            "step_id": "run-1:step:start",
            "run_state": "completed",
            "workload_id": "review.run",
            "workload_version": "v0",
            "attempt_state": "attempt_completed",
            "policy_snapshot_id": "review-run-policy:run-1",
            "configuration_snapshot_id": "review-run-config:run-1",
            "step_kind": "review_run_start",
        }
        control_plane.update(control_plane_overrides)
        return ReviewRunResult(
            ok=True,
            run_id="run-1",
            artifact_dir=str(tmp_path / "workspace" / "default" / "review_runs" / "run-1"),
            snapshot_digest="sha256:snapshot",
            policy_digest="sha256:policy",
            deterministic_decision="pass",
            deterministic_findings=0,
            model_assisted_enabled=False,
            manifest={
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "run-1:attempt:0001",
                "control_plane_step_id": "run-1:step:start",
            },
            control_plane=control_plane,
        )

    monkeypatch.setattr("orket.interfaces.orket_bundle_cli.ReviewRunService.run_diff", _fake_run_diff)

    code = main(
        [
            "review",
            "diff",
            "--repo-root",
            str(tmp_path),
            "--base",
            "base",
            "--head",
            "head",
            "--workspace",
            str(tmp_path / "workspace" / "default"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_REVIEW_RUN_FAILED"
    assert expected_error in payload["errors"][0]["message"]


def test_review_diff_cli_returns_structured_error_on_orphaned_manifest_control_plane_refs(tmp_path: Path, capsys, monkeypatch) -> None:
    """contract: diff CLI must surface structured failure when result serialization detects orphaned manifest ids."""

    def _fake_run_diff(self, **_kwargs):  # type: ignore[no-untyped-def]
        return ReviewRunResult(
            ok=True,
            run_id="run-1",
            artifact_dir=str(tmp_path / "workspace" / "default" / "review_runs" / "run-1"),
            snapshot_digest="sha256:snapshot",
            policy_digest="sha256:policy",
            deterministic_decision="pass",
            deterministic_findings=0,
            model_assisted_enabled=False,
            manifest={
                "run_id": "run-1",
                "execution_state_authority": "control_plane_records",
                "lane_outputs_execution_state_authoritative": False,
                "control_plane_run_id": "run-1",
                "control_plane_attempt_id": "",
                "control_plane_step_id": "run-1:step:start",
            },
        )

    monkeypatch.setattr("orket.interfaces.orket_bundle_cli.ReviewRunService.run_diff", _fake_run_diff)

    code = main(
        [
            "review",
            "diff",
            "--repo-root",
            str(tmp_path),
            "--base",
            "base",
            "--head",
            "head",
            "--workspace",
            str(tmp_path / "workspace" / "default"),
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)
    assert code == 1
    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "E_REVIEW_RUN_FAILED"
    assert "review_run_manifest_control_plane_attempt_id_required" in payload["errors"][0]["message"]


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
