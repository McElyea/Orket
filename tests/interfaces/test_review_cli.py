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
