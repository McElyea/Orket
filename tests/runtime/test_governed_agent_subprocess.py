# Layer: integration

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentHostBroker,
    GovernedAgentModelObservation,
)
from orket.application.services.governed_agent_operator_service import GovernedAgentOperatorService
from orket.core.contracts.governed_agent_ports import GovernedAgentInvocationOutcome
from orket.core.domain import RunState
from orket.extensions.governed_agent_invoker import GovernedAgentSubprocessInvoker
from orket_extension_sdk.agent_fixtures import prefixed_digest
from tests.runtime.governed_agent_test_support import (
    TEMPLATE_ROOT,
    DeterministicModelProvider,
    UnexpectedBroker,
    agent_request,
    binding_for,
    prepare_authority,
    resolved_profiles,
)

pytestmark = pytest.mark.integration


class _RepairingModelProvider(DeterministicModelProvider):
    async def call(self, *, request, profile):
        self.roles.append(request.role)
        if request.call_id == "planner-1":
            return GovernedAgentModelObservation(
                response=None,
                usage_posture="estimated",
                input_tokens=1,
                output_tokens=1,
                estimate_source="repair_test.v1",
                latency_ms=1,
                finish_reason="fixture_invalid",
                status="failed",
                normalized_reason="model_response_invalid_json",
            )
        return await super(DeterministicModelProvider, self).call(request=request, profile=profile)


@pytest.mark.asyncio
async def test_real_child_uses_durable_host_broker_and_returns_acceptable_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    request = agent_request()
    binding = binding_for(request)
    repository = await prepare_authority(tmp_path / "agent.sqlite3", request, binding)
    provider = DeterministicModelProvider()
    broker = GovernedAgentHostBroker(
        iteration_repository=repository,
        call_repository=repository,
        model_provider=provider,
        model_profiles=resolved_profiles(),
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent",
        allowed_stdlib_modules=("json",),
        broker=broker,
        handshake_timeout_seconds=2,
    )

    outcome = await invoker.invoke_once(binding=binding, request_payload=request)

    assert outcome.status == "returned", (
        f"{outcome.normalized_reason}; roles={provider.roles}; stderr={invoker.last_diagnostic_tail}"
    )
    assert outcome.child_confirmed_stopped is True
    assert provider.roles == ["planner", "actor", "critic"]
    assert outcome.result_payload is not None
    assert outcome.result_payload["completion_recommendation"] == "continue"
    assert len(outcome.result_payload["model_receipts"]) == 3
    records = await AsyncGovernedAgentRepository(tmp_path / "agent.sqlite3").list_call_records(
        invocation_id=binding.invocation_id
    )
    assert [record.status for record in records] == ["completed", "completed", "completed"]
    acceptance = await repository.accept_result(
        outcome=GovernedAgentInvocationOutcome(
            status="returned",
            binding=binding,
            result_payload=outcome.result_payload,
            result_digest=outcome.result_digest,
            normalized_reason=None,
            child_confirmed_stopped=True,
        )
    )
    assert acceptance.status == "accepted"


@pytest.mark.asyncio
async def test_real_child_repairs_failed_structured_output_within_issued_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    """Layer: integration. A failed model result consumes one durable, bounded repair call."""
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    request = agent_request()
    budget = request["remaining_iteration_budget"]
    budget["model_calls"] = 4
    budget["per_role_model_calls"] = [
        {"role": "planner", "count": 2},
        {"role": "actor", "count": 1},
        {"role": "critic", "count": 1},
    ]
    budget["repair_attempts"] = 1
    budget["snapshot_digest"] = prefixed_digest(
        {key: value for key, value in budget.items() if key != "snapshot_digest"}
    )
    binding = binding_for(request)
    repository = await prepare_authority(tmp_path / "repair.sqlite3", request, binding)
    provider = _RepairingModelProvider()
    broker = GovernedAgentHostBroker(
        iteration_repository=repository,
        call_repository=repository,
        model_provider=provider,
        model_profiles=resolved_profiles(),
    )
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=TEMPLATE_ROOT,
        entrypoint="governed_agent:GovernedTicketAgent",
        allowed_stdlib_modules=("json",),
        broker=broker,
        handshake_timeout_seconds=2,
    )

    outcome = await invoker.invoke_once(binding=binding, request_payload=request)

    assert outcome.status == "returned", outcome.normalized_reason
    assert provider.roles == ["planner", "planner", "actor", "critic"]
    assert outcome.result_payload is not None
    assert outcome.result_payload["invocation_status"] == "returned"
    assert outcome.result_payload["usage"]["repair_attempts"] == 1
    assert [item["status"] for item in outcome.result_payload["model_receipts"]] == [
        "failed",
        "returned",
        "returned",
        "returned",
    ]


@pytest.mark.asyncio
# Layer: integration
async def test_host_cancellation_reaps_blocked_child(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORKET_DISABLE_SANDBOX", "1")
    extension_root = tmp_path / "slow-agent"
    extension_root.mkdir()
    extension_root.joinpath("slow_agent.py").write_text(
        "from __future__ import annotations\n"
        "import asyncio\n"
        "class SlowAgent:\n"
        "    async def run(self, context):\n"
        "        await context.cancellation.wait()\n"
        "        await asyncio.sleep(60)\n",
        encoding="utf-8",
    )
    request = agent_request()
    binding = binding_for(request)
    db_path = tmp_path / "cancel.sqlite3"
    repository = await prepare_authority(db_path, request, binding)
    invoker = GovernedAgentSubprocessInvoker(
        extension_root=extension_root,
        entrypoint="slow_agent:SlowAgent",
        allowed_stdlib_modules=("asyncio",),
        broker=UnexpectedBroker(),  # type: ignore[arg-type]
        handshake_timeout_seconds=2,
    )
    invocation = asyncio.create_task(invoker.invoke_once(binding=binding, request_payload=request))
    await asyncio.sleep(0.25)
    operator = GovernedAgentOperatorService(
        transactions=SQLiteControlPlaneTransactions(db_path),
        iteration_repository=repository,
        invoker=invoker,
    )
    cancelled = await operator.cancel_run(
        run_id=binding.run_id,
        action_id="operator-action:cancel-1",
        actor_ref="operator:test",
        timestamp_utc=datetime.now(UTC).isoformat(),
        reason="test cancellation",
        cancellation_epoch=1,
        grace_period_seconds=0.1,
    )
    outcome = await invocation

    assert cancelled.child_confirmed_stopped is True
    assert cancelled.run.lifecycle_state is RunState.CANCELLED
    assert cancelled.final_truth.closure_basis.value == "cancelled_by_authority"
    assert outcome.status == "cancelled"
    assert outcome.child_confirmed_stopped is True
