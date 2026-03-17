from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys


async def _run_script(script_path: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return int(process.returncode or 0), stdout.decode("utf-8"), stderr.decode("utf-8")


def _run_torture_script() -> dict:
    returncode, stdout, stderr = asyncio.run(_run_script("scripts/nervous_system/run_nervous_system_attack_torture_pack.py"))
    assert returncode == 0, stdout + "\n" + stderr
    artifact_path = Path("benchmarks/results/nervous_system/nervous_system_attack_torture_evidence.json")
    assert artifact_path.exists()
    return json.loads(artifact_path.read_bytes().decode("utf-8"))


def _scenario(payload: dict, case_id: str) -> dict:
    for row in list(payload.get("scenarios") or []):
        if isinstance(row, dict) and str(row.get("id") or "") == case_id:
            return row
    raise AssertionError(f"scenario {case_id} not found")


def test_torture_pack_runner_produces_passing_evidence() -> None:
    payload = _run_torture_script()
    summary = dict(payload.get("summary") or {})
    adapter = dict(payload.get("adapter_run") or {})

    assert payload.get("policy_flag_mode") == "resolver_canonical"
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
