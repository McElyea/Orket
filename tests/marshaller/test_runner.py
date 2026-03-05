import json
from pathlib import Path
import subprocess
import sys

import pytest

from orket.marshaller.canonical import hash_canonical_json
from orket.marshaller.rejection_codes import FLAKE_DETECTED, TESTS_FAILED
from orket.marshaller.replay import replay_run
from orket.marshaller.runner import MarshallerRunner


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


def _run_request_payload(repo: Path, gate_commands: dict[str, list[str]], *, flake_policy: dict | None = None) -> dict:
    return {
        "repo_path": str(repo),
        "task_spec": {
            "policy_version": "v0",
            "policy_digest": "policy-1",
            "gate_commands": gate_commands,
            "flake_policy": flake_policy or {"mode": "retry_then_deny", "max_retries": 2},
        },
        "checks": list(gate_commands.keys()),
        "seed": 1,
        "max_attempts": 1,
        "execution_envelope": {
            "mode": "lockfile",
            "lockfile_digest": "sha256:lock",
        },
    }


def _proposal_payload(base_revision: str, patch: str) -> dict:
    return {
        "proposal_id": "proposal-1",
        "proposal_contract_version": "v0",
        "base_revision_digest": base_revision,
        "patch": patch,
        "intent": "update text",
        "touched_paths": ["app.txt"],
        "rationale": "test change",
    }


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_ledger(path: Path) -> list[dict]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def _assert_ledger_chain(records: list[dict]) -> None:
    prev = ""
    for record in records:
        assert record["prev_entry_digest"] == prev
        actual = record["entry_digest"]
        payload = dict(record)
        payload.pop("entry_digest")
        assert actual == hash_canonical_json(payload)
        prev = actual


@pytest.mark.asyncio
async def test_runner_accepts_when_patch_and_gates_pass(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello world\n")
    runner = MarshallerRunner(tmp_path)

    run_request = _run_request_payload(
        repo,
        {
            "build": [sys.executable, "-c", "import pathlib; pathlib.Path('app.txt').read_text()"],
            "test": [sys.executable, "-c", "import sys; sys.exit(0)"],
        },
    )
    proposal = _proposal_payload(head, patch)

    outcome = await runner.execute_once(
        run_id="run-success",
        run_request_payload=run_request,
        proposal_payload=proposal,
        allowed_paths=("app.txt",),
    )

    assert outcome.accept is True
    decision = _read_json(Path(outcome.decision_path))
    assert decision["accept"] is True
    ledger = _read_ledger(Path(outcome.run_path) / "ledger.jsonl")
    assert len(ledger) == 4
    _assert_ledger_chain(ledger)
    replay = await replay_run(Path(outcome.run_path))
    assert replay["equivalence_key_match"] is True


@pytest.mark.asyncio
async def test_runner_rejects_when_test_gate_fails(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello gate fail\n")
    runner = MarshallerRunner(tmp_path)

    run_request = _run_request_payload(
        repo,
        {
            "test": [sys.executable, "-c", "import sys; sys.exit(1)"],
        },
    )
    proposal = _proposal_payload(head, patch)

    outcome = await runner.execute_once(
        run_id="run-test-fail",
        run_request_payload=run_request,
        proposal_payload=proposal,
        allowed_paths=("app.txt",),
    )

    assert outcome.accept is False
    assert outcome.primary_rejection_code == TESTS_FAILED
    decision = _read_json(Path(outcome.decision_path))
    assert decision["primary_rejection_code"] == TESTS_FAILED


@pytest.mark.asyncio
async def test_runner_marks_flake_when_retry_outcomes_disagree(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    patch = _make_patch(repo, "hello flake\n")
    runner = MarshallerRunner(tmp_path)

    flaky_script = (
        "from pathlib import Path; import sys; "
        "p=Path('flake.flag'); "
        "exists=p.exists(); "
        "p.write_text('1', encoding='utf-8'); "
        "sys.exit(0 if exists else 1)"
    )
    run_request = _run_request_payload(
        repo,
        {
            "test": [sys.executable, "-c", flaky_script],
        },
        flake_policy={"mode": "retry_then_deny", "max_retries": 1},
    )
    proposal = _proposal_payload(head, patch)

    outcome = await runner.execute_once(
        run_id="run-flake",
        run_request_payload=run_request,
        proposal_payload=proposal,
        allowed_paths=("app.txt",),
    )

    assert outcome.accept is False
    assert outcome.primary_rejection_code == FLAKE_DETECTED
    decision = _read_json(Path(outcome.decision_path))
    assert decision["primary_rejection_code"] == FLAKE_DETECTED
