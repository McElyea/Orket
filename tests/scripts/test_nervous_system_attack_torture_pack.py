from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _run_torture_script() -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/nervous_system/run_nervous_system_attack_torture_pack.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    artifact_path = Path("benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json")
    assert artifact_path.exists()
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _scenario(payload: dict, case_id: str) -> dict:
    for row in list(payload.get("scenarios") or []):
        if isinstance(row, dict) and str(row.get("id") or "") == case_id:
            return row
    raise AssertionError(f"scenario {case_id} not found")


def test_torture_pack_runner_produces_passing_evidence() -> None:
    payload = _run_torture_script()
    summary = dict(payload.get("summary") or {})
    adapter = dict(payload.get("adapter_run") or {})

    assert adapter.get("status") == "ok"
    assert int(summary.get("total_cases") or 0) > 0
    assert int(summary.get("failed_cases") or 0) == 0
    assert int(summary.get("passed_cases") or 0) == int(summary.get("total_cases") or 0)


def test_torture_pack_includes_expected_token_replay_signal() -> None:
    payload = _run_torture_script()
    row = _scenario(payload, "autonomy_credentialed_action_requires_approval")
    token_checks = dict(row.get("token_checks") or {})

    assert token_checks.get("first_consume_ok") is True
    assert token_checks.get("replay_ok") is False
    assert token_checks.get("replay_reason_code") == "TOKEN_REPLAY"
