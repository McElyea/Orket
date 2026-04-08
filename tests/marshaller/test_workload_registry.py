from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from orket.workloads import is_builtin_workload, run_builtin_workload, validate_builtin_workload_start


class _FakeInteractionContext:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.commits: list[object] = []

    async def emit_event(self, event_type, payload):
        self.events.append((str(event_type), dict(payload)))

    async def request_commit(self, intent):
        self.commits.append(intent)


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


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8", newline="\n")
    return path


def _make_patch(repo: Path, new_content: str) -> str:
    target = repo / "app.txt"
    target.write_text(new_content, encoding="utf-8", newline="\n")
    patch = _git(repo, "diff", "HEAD", strip=False)
    _git(repo, "checkout", "--", "app.txt")
    return patch


def test_marshaller_workload_is_builtin() -> None:
    assert is_builtin_workload("marshaller_v0")


def test_validate_marshaller_workload_start_rejects_missing_paths() -> None:
    with pytest.raises(ValueError, match="run_request_path"):
        validate_builtin_workload_start(
            workload_id="marshaller_v0",
            input_config={},
            turn_params={},
        )


@pytest.mark.asyncio
async def test_run_builtin_marshaller_workload(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "workload run\n")
    run_request_path = _write_json(
        tmp_path / "run_request.json",
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
    input_config = {
        "run_request_path": str(run_request_path),
        "proposal_paths": [str(proposal_path)],
        "run_id": "workload-marshaller-run",
        "allowed_paths": ["app.txt"],
        "workspace_root": str(tmp_path),
    }
    validate_builtin_workload_start(
        workload_id="marshaller_v0",
        input_config=input_config,
        turn_params={},
    )
    ctx = _FakeInteractionContext()
    hints = await run_builtin_workload(
        workload_id="marshaller_v0",
        input_config=input_config,
        turn_params={},
        interaction_context=ctx,
    )
    assert hints == {"post_finalize_wait_ms": 0}
    run_dir = tmp_path / "workspace" / "default" / "stabilizer" / "run" / "workload-marshaller-run"
    assert run_dir.exists()
    assert (run_dir / "summary.json").exists()
    assert len(ctx.events) >= 2
    token_delta_payload = next(payload for _event_name, payload in ctx.events if "delta" in payload)
    assert token_delta_payload["delta"] == "marshaller result: accept=True attempts=1"
    assert len(ctx.commits) == 1
