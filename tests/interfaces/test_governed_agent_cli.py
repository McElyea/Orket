# Layer: integration

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from orket.application.services.governed_agent_ports import GovernedAgentInvocationOutcome
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)
from orket.interfaces.orket_bundle_cli import main
from orket_extension_sdk.agent_fixtures import agent_iteration_result, prefixed_digest
from tests.runtime.governed_agent_test_support import agent_request, binding_for, prepare_authority


def _decision_inputs() -> GovernedAgentContinuationInputs:
    return GovernedAgentContinuationInputs(
        valid_recorded_result=True,
        effect_approval_required=False,
        unresolved_effect_boundary=False,
        policy_violation=False,
        quarantine_required=False,
        accepted_cancel=False,
        accepted_terminal_stop=False,
        verified_objective_satisfied=False,
        verification_evidence_sufficient=False,
        deadline_expired=False,
        lease_expired=False,
        capability_budget_exhausted=False,
        effect_budget_exhausted=False,
        iteration_budget_exhausted=False,
        model_budget_exhausted=False,
        token_budget_exhausted=False,
        output_budget_exhausted=False,
        artifact_budget_exhausted=False,
        unrecoverable_execution_failure=False,
        repeated_state_threshold_hit=False,
        no_progress_threshold_hit=False,
        extension_recommendation="continue",
    )


async def _prepare_decided_run(db_path: Path) -> None:
    request = agent_request()
    binding = binding_for(request)
    repository = await prepare_authority(db_path, request, binding)
    result = agent_iteration_result()
    result["model_receipts"] = []
    result["effect_proposals"] = []
    result["usage"] = {
        **result["usage"],
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "charged_input_tokens": 0,
        "charged_output_tokens": 0,
        "effect_proposals": 0,
    }
    outcome = GovernedAgentInvocationOutcome(
        status="returned",
        binding=binding,
        result_payload=result,
        result_digest=prefixed_digest(result),
        normalized_reason=None,
        child_confirmed_stopped=True,
    )
    assert (await repository.accept_result(outcome=outcome)).status == "accepted"
    inputs = _decision_inputs()
    decision = decide_governed_agent_continuation(inputs)
    assert (
        await repository.publish_continuation_decision(
            binding=binding,
            accepted_result_digest=str(outcome.result_digest),
            decision_inputs=inputs.to_payload(),
            decision_payload=decision.to_payload(),
        )
    ).status == "accepted"


def test_agent_inspect_and_replay_commands_read_durable_state(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare_decided_run(db_path))

    inspect_exit = main(["agent", "inspect", "run-1", "--db", str(db_path), "--json"])
    inspection = json.loads(capsys.readouterr().out)
    replay_exit = main(["agent", "replay", "run-1", "--db", str(db_path), "--json"])
    replay = json.loads(capsys.readouterr().out)

    assert inspect_exit == 0
    assert inspection["iterations"][0]["state"] == "decided"
    assert replay_exit == 0
    assert replay["status"] == "matched"


def test_agent_cancel_command_publishes_terminal_operator_truth(tmp_path: Path, capsys) -> None:
    db_path = tmp_path / "cancel.sqlite3"
    request = agent_request()
    binding = binding_for(request)
    asyncio.run(prepare_authority(db_path, request, binding))

    exit_code = main(
        [
            "agent",
            "cancel",
            "run-1",
            "--db",
            str(db_path),
            "--action-id",
            "operator-action:cli-cancel",
            "--actor-ref",
            "operator:cli",
            "--timestamp-utc",
            "2026-09-07T12:00:00Z",
            "--reason",
            "operator request",
            "--cancellation-epoch",
            "1",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["run"]["lifecycle_state"] == "cancelled"
    assert payload["final_truth"]["closure_basis"] == "cancelled_by_authority"


def test_agent_submit_runs_catalog_resolved_deterministic_fixture(tmp_path: Path, capsys) -> None:
    template_root = Path("docs/templates/governed_agent_external").resolve()
    manifest_path = template_root / "extension.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    catalog_path = tmp_path / "extensions.json"
    catalog_path.write_text(
        json.dumps(
            {
                "extensions": [
                    {
                        "extension_id": manifest["extension_id"],
                        "extension_version": manifest["extension_version"],
                        "extension_api_version": "1.0.0",
                        "source": "test-fixture",
                        "path": str(template_root),
                        "contract_style": "sdk_v0",
                        "manifest_path": str(manifest_path),
                        "allowed_stdlib_modules": manifest["allowed_stdlib_modules"],
                        "manifest_entries": manifest["workloads"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    request = agent_request()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    db_path = tmp_path / "agent.sqlite3"
    now = datetime.now(UTC)

    exit_code = main(
        [
            "agent",
            "submit",
            "governed-agent-loop",
            "--db",
            str(db_path),
            "--catalog",
            str(catalog_path),
            "--request",
            str(request_path),
            "--creation-timestamp-utc",
            now.isoformat(),
            "--decision-timestamp-utc",
            (now + timedelta(seconds=1)).isoformat(),
            "--decision-timestamp-utc",
            (now + timedelta(seconds=2)).isoformat(),
            "--next-lease-expires-at-utc",
            (now + timedelta(seconds=7)).isoformat(),
            "--deterministic-fixture",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["proof_posture"] == "deterministic_fixture_not_live_model"
    assert payload["run"]["lifecycle_state"] == "completed"
    assert [item["disposition"] for item in payload["decisions"]] == ["continue", "complete"]
