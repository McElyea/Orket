from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _run_live_script() -> dict:
    result = subprocess.run(
        [sys.executable, "scripts/MidTier/run_nervous_system_live_evidence.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
    artifact_path = Path("benchmarks/results/nervous_system_live_evidence.json")
    assert artifact_path.exists()
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _scope_digests_by_scenario(payload: dict) -> dict[str, str]:
    scenarios = list(payload.get("scenarios") or [])
    values: dict[str, str] = {}
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        name = str(scenario.get("name") or "").strip()
        digest = str(scenario.get("scope_digest") or "").strip()
        if name and digest:
            values[name] = digest
    return values


def _scenario_by_name(payload: dict, name: str) -> dict:
    for scenario in list(payload.get("scenarios") or []):
        if isinstance(scenario, dict) and str(scenario.get("name") or "") == name:
            return scenario
    raise AssertionError(f"scenario '{name}' not found")


def test_live_evidence_scope_digest_stable_across_runs() -> None:
    first = _run_live_script()
    second = _run_live_script()

    first_scope = _scope_digests_by_scenario(first)
    second_scope = _scope_digests_by_scenario(second)

    assert first_scope
    assert second_scope
    assert first_scope == second_scope


def test_live_evidence_rejected_scenario_has_no_execution_validation_events() -> None:
    payload = _run_live_script()
    blocked = _scenario_by_name(payload, "blocked_destructive")
    event_map = dict(blocked.get("required_event_digests") or {})

    assert blocked.get("admission_decision") == "REJECT"
    assert blocked.get("commit_status") == "REJECTED_POLICY"
    assert blocked.get("commit_invoked") is True
    assert list(event_map.get("action.executed") or []) == []
    assert list(event_map.get("action.result_validated") or []) == []


def test_live_evidence_token_replay_scenario_records_deterministic_failure() -> None:
    payload = _run_live_script()
    replay = _scenario_by_name(payload, "credentialed_token_replay")
    event_map = dict(replay.get("required_event_digests") or {})

    assert replay.get("token_replay_reason_code") == "TOKEN_REPLAY"
    assert replay.get("token_replay_consume_ok") is False
    assert replay.get("commit_status") == "REJECTED_POLICY"
    assert len(list(event_map.get("credential.token_used") or [])) == 1
