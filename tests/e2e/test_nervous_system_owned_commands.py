"""Layer: end_to_end. Real script CLIs and Kernel effects; adapters are declared fixtures."""
import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

from orket.application.services.command_process_supervisor import CommandProcessSupervisor

pytestmark = [pytest.mark.end_to_end, pytest.mark.asyncio]
ROOT = Path(__file__).resolve().parents[2]


def _stage(root):
    (root / "tools").mkdir()
    for name in ("fake_openclaw_adapter_strict.py", "fake_challenge_corpus_adapter.py"):
        shutil.copy2(ROOT / "tools" / name, root / "tools" / name)
    corpus = root / "benchmarks/scenarios/nervous_system_attack_corpus.json"
    corpus.parent.mkdir(parents=True)
    shutil.copy2(ROOT / "benchmarks/scenarios/nervous_system_attack_corpus.json", corpus)


@pytest.mark.parametrize("route", ["live", "torture"])
async def test_nervous_system_cli_keeps_real_fixture_exchange_and_kernel_outcomes(tmp_path, route):
    await asyncio.to_thread(_stage, tmp_path)
    filename = "run_nervous_system_live_evidence.py" if route == "live" else "run_nervous_system_attack_torture_pack.py"
    output = (tmp_path / "benchmarks/results/nervous_system/nervous_system_live_evidence.json"
              if route == "live" else tmp_path / "torture.json")
    corpus_path = tmp_path / "benchmarks/scenarios/nervous_system_attack_corpus.json"
    arguments = [] if route == "live" else ["--corpus", str(corpus_path), "--out", str(output)]
    result = await CommandProcessSupervisor(tmp_path, cancellation_event="nervous_system_cli_interrupted").run(
        [sys.executable, "-I", str(ROOT / "scripts/nervous_system" / filename), *arguments], cwd=tmp_path,
        environment=dict(os.environ, ORKET_DISABLE_SANDBOX="1"), timeout_seconds=30)
    assert result.cleanup_confirmed and result.capture_complete
    assert result.reason == "completed" and result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    artifact = json.loads(await asyncio.to_thread(output.read_text, encoding="utf-8"))
    exchange = artifact["adapter_run"]
    assert exchange["status"] == "ok" and exchange["failed_at"] is None
    assert exchange["request_count"] == exchange["response_count"] == exchange["completed_count"]
    assert artifact["diff_ledger"]
    if route == "torture":
        corpus = json.loads(await asyncio.to_thread(corpus_path.read_text, encoding="utf-8"))
        assert artifact["summary"] == {"total_cases": len(corpus["cases"]), "passed_cases": len(corpus["cases"]), "failed_cases": 0}
    else:
        assert exchange["completed_count"] == 4 and len(artifact["scenarios"]) == 4
        assert {row["name"]: (row["admission_decision"], row["commit_status"]) for row in artifact["scenarios"]} == {
            "blocked_destructive": ("REJECT", "REJECTED_POLICY"),
            "approval_required": ("NEEDS_APPROVAL", "COMMITTED"),
            "credentialed_token": ("NEEDS_APPROVAL", "COMMITTED"),
            "credentialed_token_replay": ("NEEDS_APPROVAL", "REJECTED_POLICY"),
        }
        replay = next(row for row in artifact["scenarios"] if row["name"] == "credentialed_token_replay")
        assert replay["token_consume_ok"] and not replay["token_replay_consume_ok"]
        assert replay["token_replay_reason_code"] == "TOKEN_REPLAY"
