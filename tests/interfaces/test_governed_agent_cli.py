# Layer: integration

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.core.contracts.governed_agent_ports import GovernedAgentInvocationOutcome
from orket.core.contracts.governed_agent_wake_records import GovernedAgentWakeRequest
from orket.core.domain.governed_agent_continuation import (
    GovernedAgentContinuationInputs,
    decide_governed_agent_continuation,
)
from orket.interfaces.orket_bundle_cli import main
from orket_extension_sdk.agent_fixtures import agent_iteration_result, prefixed_digest
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
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
    assert payload["child_confirmed_stopped"] is False
    assert payload["final_truth"]["residual_uncertainty_classification"] == "unresolved_residual_uncertainty"


def test_agent_wake_commands_enqueue_idempotent_manual_work_and_inspect_it(tmp_path: Path, capsys) -> None:
    """Layer: integration. The public manual transport persists through the canonical wake repository."""
    request_path = tmp_path / "manual-request.json"
    request_path.write_text(json.dumps(agent_request()), encoding="utf-8")
    db_path = tmp_path / "agent.sqlite3"
    now = datetime.now(UTC)
    enqueue_args = [
        "agent", "wake", "enqueue",
        "--db", str(db_path),
        "--workload-id", "governed-agent-loop",
        "--occurrence-id", "manual-occurrence-1",
        "--request", str(request_path),
        "--creation-timestamp-utc", now.isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=1)).isoformat(),
        "--decision-timestamp-utc", (now + timedelta(seconds=2)).isoformat(),
        "--next-lease-expires-at-utc", (now + timedelta(seconds=7)).isoformat(),
        "--json",
    ]

    first_exit = main(enqueue_args)
    first = json.loads(capsys.readouterr().out)
    repeated_exit = main(enqueue_args)
    repeated = json.loads(capsys.readouterr().out)
    list_exit = main(["agent", "wake", "list", "--db", str(db_path), "--json"])
    listed = json.loads(capsys.readouterr().out)
    inspect_exit = main(
        ["agent", "wake", "inspect", first["wake"]["wake_id"], "--db", str(db_path), "--json"]
    )
    inspected = json.loads(capsys.readouterr().out)

    assert first_exit == repeated_exit == list_exit == inspect_exit == 0
    assert first["status"] == "enqueued"
    assert repeated["status"] == "idempotent"
    assert first["wake"]["source"] == "manual"
    assert listed["items"] == [first["wake"]]
    assert inspected["wake"] == first["wake"]


def test_agent_wake_cli_cancels_and_resolves_uncertain_claim(tmp_path: Path, capsys) -> None:
    """Layer: integration. CLI controls publish durable evidence-bearing transitions."""
    db_path = tmp_path / "agent.sqlite3"
    asyncio.run(_prepare_claimed_wake(db_path))

    cancel_exit = main(
        [
            "agent", "wake", "cancel", "wake-cli-control", "--db", str(db_path),
            "--action-id", "wake-action:cli-cancel", "--actor-ref", "operator:cli",
            "--timestamp-utc", "2026-09-07T12:00:02Z", "--reason", "operator request",
            "--expected-cancellation-epoch", "0", "--cancellation-epoch", "1", "--json",
        ]
    )
    cancelled = json.loads(capsys.readouterr().out)
    recover_exit = main(
        [
            "agent", "wake", "recover", "wake-cli-control", "--db", str(db_path),
            "--action-id", "wake-action:cli-recover", "--actor-ref", "operator:cli",
            "--timestamp-utc", "2026-09-07T12:00:03Z", "--reason", "reconciled",
            "--expected-fencing-generation", "1", "--resolution", "confirm_cancelled",
            "--child-confirmed-stopped", "--effect-uncertainty-cleared",
            "--evidence-ref", "process-reap:cli", "--evidence-ref", "effect-check:cli", "--json",
        ]
    )
    recovered = json.loads(capsys.readouterr().out)
    actions_exit = main(
        ["agent", "wake", "actions", "wake-cli-control", "--db", str(db_path), "--json"]
    )
    actions = json.loads(capsys.readouterr().out)

    assert cancel_exit == recover_exit == actions_exit == 0
    assert cancelled["wake"]["uncertainty"] is True
    assert recovered["wake"]["state"] == "cancelled"
    assert recovered["wake"]["uncertainty"] is False
    assert [item["action_id"] for item in actions["items"]] == [
        "wake-action:cli-cancel",
        "wake-action:cli-recover",
    ]
    assert actions["items"][-1]["request"]["evidence_refs"] == [
        "process-reap:cli",
        "effect-check:cli",
    ]


async def _prepare_claimed_wake(db_path: Path) -> None:
    repository = AsyncGovernedAgentWakeRepository(db_path)
    await repository.enqueue(
        GovernedAgentWakeRequest(
            wake_id="wake-cli-control",
            source="manual",
            target_kind="existing_run",
            target_run_id="run-1",
            workload_id=None,
            occurrence_id="cli-control",
            deduplication_key="manual:run-1:cli-control",
            payload={"reason": "operator_requested"},
            created_at_utc="2026-09-07T12:00:00Z",
        )
    )
    claim = await repository.claim_next(
        owner_id="supervisor:cli",
        now_utc="2026-09-07T12:00:01Z",
        lease_expires_at_utc="2026-09-07T12:01:01Z",
        max_active_claims=1,
    )
    assert claim.status == "claimed"


def test_agent_submit_runs_catalog_resolved_deterministic_fixture(tmp_path: Path, capsys, elapsed_agent_clock) -> None:
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
    # This completion case starts two real interpreters. Short expiry has separate
    # acceptance cases; preserve elapsed time while giving this request 30 seconds.
    now = datetime.now(UTC)
    request["deadline_utc"] = (now + timedelta(seconds=30)).isoformat()
    request["lease_expires_at_utc"] = (now + timedelta(seconds=25)).isoformat()
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    db_path = tmp_path / "agent.sqlite3"

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
            (now + timedelta(seconds=29)).isoformat(),
            "--deterministic-fixture",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0, payload
    assert payload["proof_posture"] == "deterministic_fixture_not_live_model"
    assert payload["run"]["lifecycle_state"] == "completed"
    assert [item["disposition"] for item in payload["decisions"]] == ["continue", "complete"]
