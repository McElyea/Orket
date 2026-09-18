# Layer: integration; real subprocess and SQLite, deterministic inference
from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime, timedelta

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.governed_agent_broker_service import GovernedAgentHostBroker
from orket.application.services.governed_agent_loop_service import GovernedAgentLoopService
from orket.core.domain import RunState
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk.agent_fixtures import prefixed_digest
from scripts.common.rerun_diff_ledger import write_payload_with_diff_ledger
from tests.helpers.governed_agent_clock import elapsed_agent_clock as elapsed_agent_clock
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    SecondIterationVerifier,
    agent_workload_record,
    resolved_profiles,
    staged_agent_request,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio, pytest.mark.usefixtures("elapsed_agent_clock")]


@pytest.mark.parametrize("case", ["wrong-totals", "false-completion", "repeated-state"])
async def test_fixed_negative_acceptance_cases_remain_host_governed(tmp_path, monkeypatch, case):
    """Layer: integration. Adversarial child output cannot grant effects, completion, or endless progress."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    source = await asyncio.to_thread((TEMPLATE_ROOT / "governed_agent.py").read_text, encoding="utf-8")
    request = staged_agent_request()
    if case == "wrong-totals":
        source = source.replace("advisory_proposal=canonical_json(critic.response.thaw())",
                                'advisory_proposal=\'{"counts":{"open":999},"source_refs":["artifact:ticket-batch-a"]}\'')
        request["namespace_scope"] = ["issue:issue-1"]
        request["admitted_capabilities"] = ["agent.iteration.v1", "read_file", "write_file"]
        request["extension_config"] = {"effect_demo": {"enabled": True, "namespace": "issue:issue-1",
                                                      "read_path": "input.json", "write_path": "report.json"}}
        for scope in ("remaining_run_budget", "remaining_iteration_budget"):
            request[scope]["per_capability_effects"] = [{"capability": name, "count": 1}
                                                       for name in ("read_file", "write_file")]
    elif case == "false-completion":
        source = source.replace('completion_recommendation="pause" if effects else "continue"',
                                'completion_recommendation="complete"')
    else:
        budget = request["remaining_run_budget"]
        for key in ("iterations", "model_calls", "input_tokens", "output_tokens"):
            budget[key] *= 2
        for counter in budget["per_role_model_calls"]:
            counter["count"] *= 2
        budget["repeated_states"] = budget["no_progress_iterations"] = 1
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        budget = request[scope]
        budget["snapshot_digest"] = prefixed_digest({key: value for key, value in budget.items()
                                                    if key != "snapshot_digest"})
    execution, repository = await _run(tmp_path, source, request)
    if case == "wrong-totals":
        assert execution.run.lifecycle_state is RunState.RECOVERY_PENDING
        assert execution.decisions[-1].rule == "unsafe_or_unresolved_boundary"
    elif case == "false-completion":
        assert execution.run.lifecycle_state is RunState.OPERATOR_BLOCKED
        assert execution.decisions[-1].rule == "completion_evidence_insufficient"
    else:
        assert execution.run.lifecycle_state is RunState.FAILED_TERMINAL
        assert execution.decisions[-1].rule == "progress_threshold_exhausted"
        assert execution.final_truth.result_class.value == "blocked"
        snapshots = await repository.list_iteration_snapshots(run_id="run-1")
        assert len(snapshots) == 2
        assert snapshots[-1].decision_inputs["repeated_state_count"] == 1
        assert snapshots[-1].decision_inputs["no_progress_count"] == 1
    assert execution.final_truth is None or execution.final_truth.result_class.value != "success"
    assert not (tmp_path / "report.json").exists()


async def _run(tmp_path, source, request):
    started = time.monotonic_ns()
    extension = tmp_path / "extension"
    await asyncio.to_thread(extension.mkdir)
    await asyncio.to_thread((extension / "governed_agent.py").write_text, source, encoding="utf-8")
    db = tmp_path / "agent.sqlite3"
    repository = AsyncGovernedAgentRepository(db)
    broker = GovernedAgentHostBroker(iteration_repository=repository, call_repository=repository,
                                    model_provider=DeterministicModelProvider(), model_profiles=resolved_profiles())
    invoker = GovernedAgentSubprocessInvoker(extension_root=extension, entrypoint="governed_agent:GovernedTicketAgent",
                                            allowed_stdlib_modules=("json",), broker=broker)
    service = GovernedAgentLoopService(
        execution_repository=AsyncControlPlaneExecutionRepository(db), iteration_repository=repository,
        transactions=SQLiteControlPlaneTransactions(db), verifier=SecondIterationVerifier(),
        invoker=invoker,
    )
    now = datetime.now(UTC)
    count = request["remaining_run_budget"]["iterations"]
    try:
        result = await service.run_bounded(
            initial_request_payload=request, workload_record=agent_workload_record(),
            extension_digest="sha256:" + "e" * 64, configuration_digest="sha256:" + "c" * 64,
            admission_receipt_ref="agent-admission:test", creation_timestamp_utc=now.isoformat(),
            decision_timestamps_utc=[(now + timedelta(seconds=i)).isoformat() for i in range(count)],
            next_lease_expiries_utc=[request["lease_expires_at_utc"]] * (count - 1),
        )
    except (OSError, ValueError) as exc:
        await _retain_invocation_failure(tmp_path, invoker, request, started, f"{type(exc).__name__}: {exc}")
        raise
    if result.normalized_reason:
        await _retain_invocation_failure(tmp_path, invoker, request, started, result.normalized_reason)
    return result, repository


async def _retain_invocation_failure(tmp_path, invoker, request, started, reason):
    """Layer: integration support. Retain observed diagnostics without changing deadlines or outcomes."""
    await asyncio.to_thread(write_payload_with_diff_ledger, tmp_path / "native_invocation_failure.json", {
        "reason": reason,
        "elapsed_ns": time.monotonic_ns() - started,
        "request_deadline_utc": request["deadline_utc"],
        "request_lease_expires_at_utc": request["lease_expires_at_utc"],
        "last_child_diagnostic_tail": invoker.last_diagnostic_tail,
        "scope": "Observed final child diagnostic tail; absence of text does not establish the original latency cause.",
    })
