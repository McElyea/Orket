import json
from pathlib import Path
import subprocess
import sys

import pytest

from orket.marshaller.canonical import hash_canonical_json
from orket.marshaller.promotion import promote_run
from orket.marshaller.rejection_codes import FORBIDDEN_PATH
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


def _current_branch(repo: Path) -> str:
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD")


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
    promotion = await promote_run(
        Path(outcome.run_path),
        actor_id="local-user",
        actor_source="cli",
        branch=_current_branch(repo),
    )
    assert promotion["commit_sha"]
    assert promotion["tree_digest"]
    promotion_file = _read_json(Path(outcome.run_path) / "promotion.json")
    assert promotion_file["actor_type"] == "human"
    ledger_after_promotion = _read_ledger(Path(outcome.run_path) / "ledger.jsonl")
    assert ledger_after_promotion[-1]["event_type"] == "promotion_event"
    _assert_ledger_chain(ledger_after_promotion)


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


@pytest.mark.asyncio
async def test_runner_uses_next_attempt_until_acceptance(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    runner = MarshallerRunner(tmp_path)
    valid_patch = _make_patch(repo, "final text\n")

    run_request = _run_request_payload(
        repo,
        {
            "test": [sys.executable, "-c", "import sys; sys.exit(0)"],
        },
    )
    first_bad = _proposal_payload(head, valid_patch)
    first_bad["proposal_id"] = "proposal-bad"
    first_bad["touched_paths"] = ["../escape.txt"]
    second_good = _proposal_payload(head, valid_patch)
    second_good["proposal_id"] = "proposal-good"
    run_request["max_attempts"] = 2

    outcome = await runner.execute(
        run_id="run-multi",
        run_request_payload=run_request,
        proposal_payloads=[first_bad, second_good],
        allowed_paths=("app.txt",),
    )

    assert outcome.accept is True
    assert outcome.attempt_count == 2
    assert outcome.accepted_attempt_index == 2
    summary = _read_json(Path(outcome.summary_path))
    assert summary["accepted_attempt_index"] == 2
    assert summary["primary_rejection_histogram"] == {FORBIDDEN_PATH: 1}
    triage = _read_json(Path(outcome.run_path) / "triage.json")
    assert len(triage["attempts"]) == 2
    assert triage["attempts"][0]["primary_rejection_code"] == FORBIDDEN_PATH
    replay = await replay_run(Path(outcome.run_path))
    assert replay["attempt_index"] == 2
    promotion = await promote_run(
        Path(outcome.run_path),
        actor_id="local-user",
        actor_source="cli",
        branch=_current_branch(repo),
    )
    assert promotion["attempt_index"] == 2


@pytest.mark.asyncio
async def test_runner_respects_max_attempts_cap(tmp_path: Path) -> None:
    repo, head = _init_repo(tmp_path)
    runner = MarshallerRunner(tmp_path)
    patch = _make_patch(repo, "cap test\n")
    run_request = _run_request_payload(
        repo,
        {
            "test": [sys.executable, "-c", "import sys; sys.exit(0)"],
        },
    )
    run_request["max_attempts"] = 2

    bad_a = _proposal_payload(head, patch)
    bad_b = _proposal_payload(head, patch)
    bad_c = _proposal_payload(head, patch)
    bad_a["proposal_id"] = "a"
    bad_b["proposal_id"] = "b"
    bad_c["proposal_id"] = "c"
    bad_a["touched_paths"] = ["../bad-a.txt"]
    bad_b["touched_paths"] = ["../bad-b.txt"]
    bad_c["touched_paths"] = ["../bad-c.txt"]

    outcome = await runner.execute(
        run_id="run-cap",
        run_request_payload=run_request,
        proposal_payloads=[bad_a, bad_b, bad_c],
        allowed_paths=("app.txt",),
    )

    assert outcome.accept is False
    assert outcome.attempt_count == 2
    summary = _read_json(Path(outcome.summary_path))
    assert summary["attempt_count"] == 2
    assert summary["total_proposals_received"] == 3
    triage = _read_json(Path(outcome.run_path) / "triage.json")
    assert len(triage["attempts"]) == 2
