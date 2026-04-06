import json
import subprocess
import sys
from pathlib import Path

import pytest

from orket.marshaller.cli import (
    default_run_id,
    execute_marshaller_from_files,
    inspect_marshaller_attempt,
    list_marshaller_runs,
)


def _git(repo: Path, *args: str, strip: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if strip else completed.stdout


def _init_repo(tmp_path: Path) -> tuple[Path, str]:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init")
    _git(repo, "config", "user.name", "Orket Test")
    _git(repo, "config", "user.email", "orket@example.com")
    (repo / "app.txt").write_text("hello\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "app.txt")
    _git(repo, "commit", "-m", "base")
    return repo, _git(repo, "rev-parse", "HEAD")


def _make_patch(repo: Path, new_content: str) -> str:
    target = repo / "app.txt"
    target.write_text(new_content, encoding="utf-8", newline="\n")
    patch = _git(repo, "diff", "HEAD", strip=False)
    _git(repo, "checkout", "--", "app.txt")
    return patch


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    return path


@pytest.mark.asyncio
async def test_execute_marshaller_from_files_runs_and_replays(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello from cli\n")
    run_request_path = _write_json(
        tmp_path / "run_request.json",
        {
            "repo_path": str(repo),
            "task_spec": {
                "policy_version": "v0",
                "policy_digest": "policy-1",
                "gate_commands": {
                    "test": [sys.executable, "-c", "import sys; sys.exit(0)"],
                },
            },
            "checks": ["test"],
            "seed": 1,
            "max_attempts": 1,
            "execution_envelope": {"mode": "lockfile", "lockfile_digest": "sha256:lock"},
        },
    )
    proposal_path = _write_json(
        tmp_path / "proposal.json",
        {
            "proposal_id": "proposal-1",
            "proposal_contract_version": "v0",
            "base_revision_digest": head,
            "patch": patch,
            "intent": "update",
            "touched_paths": ["app.txt"],
            "rationale": "test",
        },
    )
    result = await execute_marshaller_from_files(
        workspace_root=tmp_path,
        run_request_path=run_request_path,
        proposal_paths=[proposal_path],
        run_id="run-cli",
        allowed_paths=("app.txt",),
    )

    assert result["accept"] is True
    assert result["attempt_count"] == 1
    assert result["replay_result"]["equivalence_key_match"] is True


@pytest.mark.asyncio
async def test_execute_marshaller_from_files_can_promote(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello promote cli\n")
    current_branch = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")

    run_request_path = _write_json(
        tmp_path / "run_request_promote.json",
        {
            "repo_path": str(repo),
            "task_spec": {
                "policy_version": "v0",
                "policy_digest": "policy-1",
                "gate_commands": {
                    "test": [sys.executable, "-c", "import sys; sys.exit(0)"],
                },
            },
            "checks": ["test"],
            "seed": 1,
            "max_attempts": 1,
            "execution_envelope": {"mode": "lockfile", "lockfile_digest": "sha256:lock"},
        },
    )
    proposal_path = _write_json(
        tmp_path / "proposal_promote.json",
        {
            "proposal_id": "proposal-1",
            "proposal_contract_version": "v0",
            "base_revision_digest": head,
            "patch": patch,
            "intent": "update",
            "touched_paths": ["app.txt"],
            "rationale": "test",
        },
    )
    result = await execute_marshaller_from_files(
        workspace_root=tmp_path,
        run_request_path=run_request_path,
        proposal_paths=[proposal_path],
        run_id="run-cli-promote",
        allowed_paths=("app.txt",),
        promote=True,
        actor_id="cli-user",
        actor_source="cli",
        branch=current_branch,
    )

    assert result["accept"] is True
    assert result["promotion"]["actor_id"] == "cli-user"
    assert result["promotion"]["commit_sha"]


def test_default_run_id_has_prefix() -> None:
    assert default_run_id().startswith("marshaller-")


@pytest.mark.asyncio
async def test_list_and_inspect_marshaller_runs(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello inspect cli\n")
    run_request_path = _write_json(
        tmp_path / "run_request_list.json",
        {
            "repo_path": str(repo),
            "task_spec": {
                "policy_version": "v0",
                "policy_digest": "policy-1",
                "gate_commands": {"test": [sys.executable, "-c", "import sys; sys.exit(0)"]},
            },
            "checks": ["test"],
            "seed": 1,
            "max_attempts": 1,
            "execution_envelope": {"mode": "lockfile", "lockfile_digest": "sha256:lock"},
        },
    )
    proposal_path = _write_json(
        tmp_path / "proposal_list.json",
        {
            "proposal_id": "proposal-1",
            "proposal_contract_version": "v0",
            "base_revision_digest": head,
            "patch": patch,
            "intent": "update",
            "touched_paths": ["app.txt"],
            "rationale": "test",
        },
    )
    await execute_marshaller_from_files(
        workspace_root=tmp_path,
        run_request_path=run_request_path,
        proposal_paths=[proposal_path],
        run_id="run-list-inspect",
        allowed_paths=("app.txt",),
    )
    runs = await list_marshaller_runs(tmp_path, limit=10)
    assert runs
    assert runs[0]["run_id"] == "run-list-inspect"
    inspect = await inspect_marshaller_attempt(tmp_path, run_id="run-list-inspect")
    assert inspect["attempt_index"] == 1
    assert inspect["decision"]["accept"] is True
