from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path


async def _run_script(script_path: str) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        script_path,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return int(process.returncode or 0), stdout.decode("utf-8"), stderr.decode("utf-8")


def _run_live_script() -> dict:
    returncode, stdout, stderr = asyncio.run(_run_script("scripts/nervous_system/run_nervous_system_live_evidence.py"))
    assert returncode == 0, stdout + "\n" + stderr
    artifact_path = Path("benchmarks/results/nervous_system/nervous_system_live_evidence.json")
    assert artifact_path.exists()
    return json.loads(artifact_path.read_bytes().decode("utf-8"))


def _scope_digests_by_scenario(payload: dict) -> dict[str, str]:
    values: dict[str, str] = {}
    for scenario in list(payload.get("scenarios") or []):
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


def test_live_evidence_uses_resolver_canonical_mode_and_operator_audit() -> None:
    payload = _run_live_script()
    approval = _scenario_by_name(payload, "approval_required")
    operator_surfaces = dict(approval.get("operator_surfaces") or {})
    audit = dict(operator_surfaces.get("audit_action_lifecycle") or {})
    replay = dict(operator_surfaces.get("replay_action_lifecycle") or {})
    rebuild = dict(operator_surfaces.get("rebuild_pending_approvals") or {})

    assert payload.get("policy_flag_mode") == "resolver_canonical"
    assert audit.get("ok") is True
    assert replay.get("commit_status") == "COMMITTED"
    assert replay.get("approval_status") == "APPROVED"
    assert rebuild.get("count") == 0


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
