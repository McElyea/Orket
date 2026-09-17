"""Public agent submission and operator commands retain state across native processes."""
import asyncio
from datetime import timedelta

import pytest

from orket.adapters.storage.async_governed_agent_run_control_repository import AsyncGovernedAgentRunControlRepository
from tests.helpers.governed_agent_cli import run_agent_cli, write_submission_files
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority

pytestmark = pytest.mark.end_to_end


# Layer: end-to-end
def test_native_agent_submit_replay_reentry_and_missing_run(tmp_path):
    catalog, request, now = write_submission_files(tmp_path)
    arguments = (
        "submit", "governed-agent-loop", "--catalog", str(catalog), "--request", str(request),
        "--creation-timestamp-utc", now.isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=1)).isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=2)).isoformat(),
        "--next-lease-expires-at-utc", (now + timedelta(minutes=2)).isoformat(), "--deterministic-fixture",
    )
    first = run_agent_cli(tmp_path, *arguments)
    assert first["ok"] and first["proof_posture"] == "deterministic_fixture_not_live_model"
    assert [row["disposition"] for row in first["decisions"]] == ["continue", "complete"]
    inspection = run_agent_cli(tmp_path, "inspect", "run-1")
    assert inspection["run"]["lifecycle_state"] == "completed"
    assert inspection["final_truth"] == first["final_truth"]
    assert run_agent_cli(tmp_path, "replay", "run-1")["status"] == "matched"
    repeated = run_agent_cli(tmp_path, *arguments)
    assert repeated["decisions"] == [] and repeated["final_truth"] == first["final_truth"]
    assert repeated["iterations"] == first["iterations"]
    missing = run_agent_cli(tmp_path, "inspect", "missing-run", expected=1)
    assert missing == {"ok": False, "error": "E_AGENT_RUN_NOT_FOUND"}
    request.write_text("[]", encoding="utf-8")
    malformed = run_agent_cli(tmp_path, *arguments, expected=1, db_name="malformed.sqlite3")
    assert malformed == {"ok": False, "error": "E_AGENT_REQUEST_OBJECT_REQUIRED"}
    assert not (tmp_path / "malformed.sqlite3").exists()


@pytest.mark.parametrize("command", ["pause", "stop"])
# Layer: end-to-end
def test_native_agent_control_and_cancellation_preserve_uncertainty(tmp_path, command):
    payload = agent_request()
    binding = binding_for(payload)
    asyncio.run(prepare_authority(tmp_path / "agent.sqlite3", payload, binding))
    arguments = (command, "run-1", "--action-id", "operator-control", "--actor-ref", "operator:native",
                 "--timestamp-utc", "2026-09-07T12:00:00Z", "--invocation-id", binding.invocation_id)
    assert run_agent_cli(tmp_path, *arguments)["status"] == "requested"
    assert run_agent_cli(tmp_path, *arguments)["status"] == "idempotent"
    repository = AsyncGovernedAgentRunControlRepository(tmp_path / "agent.sqlite3")
    assert len(asyncio.run(repository.list_controls(binding.invocation_id))) == 1
    cancelled = run_agent_cli(
        tmp_path, "cancel", "run-1", "--action-id", "cancel-native", "--actor-ref", "operator:native",
        "--timestamp-utc", "2026-09-07T12:00:01Z", "--reason", "requested", "--cancellation-epoch", "1",
    )
    assert cancelled["child_confirmed_stopped"] is False
    assert cancelled["final_truth"]["residual_uncertainty_classification"] == "unresolved_residual_uncertainty"
    assert run_agent_cli(tmp_path, "inspect", "run-1")["run"] == cancelled["run"]
