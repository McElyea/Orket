# Layer: integration

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_execution_repository import (
    AsyncControlPlaneExecutionRepository,
)
from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
)
from orket.adapters.storage.async_governed_agent_repository import AsyncGovernedAgentRepository
from orket.adapters.storage.async_governed_agent_wake_repository import (
    AsyncGovernedAgentWakeRepository,
)
from orket.adapters.storage.async_pending_gate_repository import AsyncPendingGateRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.adapters.tools.governed_agent_file_effect_executor import GovernedAgentFileEffectExecutor
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.governed_agent_broker_service import (
    GovernedAgentHostBroker,
    GovernedAgentModelObservation,
)
from orket.application.services.governed_agent_effect_resume_service import GovernedAgentEffectResumeService
from orket.application.services.governed_agent_effect_service import GovernedAgentEffectService
from orket.application.services.governed_agent_supervisor import GovernedAgentWakeClaimGuard
from orket.application.services.governed_agent_wake_dispatcher import (
    GovernedAgentProviderConfiguration,
    GovernedAgentWakeLoopDispatcher,
)
from orket.application.services.tool_gate_service import ToolGate
from orket.core.contracts.governed_agent_ports import GovernedAgentAuthorityStaleError
from orket.core.contracts.governed_agent_wake_records import GovernedAgentWakeRequest
from orket.extensions.manager import ExtensionManager
from orket_extension_sdk.agent_fixtures import agent_model_call_request, prefixed_digest
from tests.runtime.governed_agent_test_support import (
    agent_request,
    binding_for,
    prepare_authority,
    resolved_profiles,
)

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
# Layer: integration
async def test_dispatcher_releases_work_that_exceeds_provider_capacity(tmp_path: Path) -> None:
    """Layer: integration. Durable claim admission is narrowed by the request's provider demand."""
    db_path = tmp_path / "agent.sqlite3"
    request = agent_request()
    for scope in ("remaining_run_budget", "remaining_iteration_budget"):
        request[scope]["total_inference_concurrency"] = 2
        request[scope]["snapshot_digest"] = prefixed_digest(
            {key: value for key, value in request[scope].items() if key != "snapshot_digest"}
        )
    now = datetime.now(UTC)
    wake_request = _wake(request, now)
    wakes = AsyncGovernedAgentWakeRepository(db_path)
    await wakes.enqueue(wake_request)
    claim = await wakes.claim_next(
        owner_id="capacity-test",
        now_utc=now.isoformat(),
        lease_expires_at_utc=(now + timedelta(seconds=30)).isoformat(),
        max_active_claims=1,
    )
    assert claim.wake is not None and claim.authority is not None
    execution = AsyncControlPlaneExecutionRepository(db_path)
    iterations = AsyncGovernedAgentRepository(db_path)
    records = AsyncControlPlaneRecordRepository(db_path)
    publication = ControlPlanePublicationService(repository=records)
    dispatcher = GovernedAgentWakeLoopDispatcher(
        execution_repository=execution,
        iteration_repository=iterations,
        record_repository=records,
        extension_manager=ExtensionManager(catalog_path=tmp_path / "unused.json", project_root=tmp_path),
        provider=GovernedAgentProviderConfiguration(
            mode="deterministic_fixture",
            default_model="",
            role_models={},
            ollama_base_url="",
            inventory_timeout_seconds=1,
            capacity_limit=1,
        ),
        effect_service=GovernedAgentEffectService(
            transactions=SQLiteControlPlaneTransactions(db_path),
            execution_repository=execution,
            publication=publication,
            pending_gates=AsyncPendingGateRepository(db_path),
            file_executor=GovernedAgentFileEffectExecutor(tmp_path, tool_gate=ToolGate(None, tmp_path)),
        ),
        effect_resume_service=GovernedAgentEffectResumeService(
            execution_repository=execution,
            iteration_repository=iterations,
            publication=publication,
        ),
    )
    guard = GovernedAgentWakeClaimGuard(
        repository=wakes,
        authority=claim.authority,
        now_utc=lambda: now.isoformat(),
    )

    result = await dispatcher.dispatch(wake=claim.wake, guard=guard)

    assert result.status == "released"
    assert result.reason == "provider_capacity_unavailable"
    assert result.child_confirmed_stopped is True


@pytest.mark.asyncio
async def test_broker_does_not_publish_provider_result_after_wake_is_cancelled(tmp_path: Path) -> None:
    """Layer: integration. The wake fence is rechecked after provider return and before receipt publication."""
    db_path = tmp_path / "agent.sqlite3"
    request = agent_request()
    binding = binding_for(request)
    iterations = await prepare_authority(db_path, request, binding)
    now = datetime.now(UTC)
    wakes = AsyncGovernedAgentWakeRepository(db_path)
    await wakes.enqueue(_wake(request, now))
    claim = await wakes.claim_next(
        owner_id="fence-test",
        now_utc=now.isoformat(),
        lease_expires_at_utc=(now + timedelta(seconds=30)).isoformat(),
        max_active_claims=1,
    )
    assert claim.authority is not None
    guard = GovernedAgentWakeClaimGuard(
        repository=wakes,
        authority=claim.authority,
        now_utc=lambda: now.isoformat(),
    )

    class CancellingProvider:
        async def call(self, **_) -> GovernedAgentModelObservation:
            cancelled = await wakes.cancel_wake(
                wake_id="wake-capacity",
                expected_cancellation_epoch=0,
                cancellation_epoch=1,
                reason="operator_cancelled",
            )
            assert cancelled.status == "applied"
            return GovernedAgentModelObservation(
                response={"counts": {"open": 1}},
                usage_posture="measured",
                input_tokens=1,
                output_tokens=1,
                estimate_source=None,
                latency_ms=1,
                finish_reason="stop",
            )

    broker = GovernedAgentHostBroker(
        iteration_repository=iterations,
        call_repository=iterations,
        model_provider=CancellingProvider(),
        model_profiles=resolved_profiles(),
        authority_guard=guard,
    )

    with pytest.raises(GovernedAgentAuthorityStaleError, match="E_AGENT_WAKE_CLAIM_STALE"):
        await broker.dispatch_call(
            binding=binding,
            operation="model.call.v1",
            call_payload=agent_model_call_request(),
        )

    calls = await iterations.list_call_records(invocation_id=binding.invocation_id)
    assert len(calls) == 1
    assert calls[0].status == "reserved"
    assert calls[0].result_payload is None


def _wake(request: dict, now: datetime) -> GovernedAgentWakeRequest:
    return GovernedAgentWakeRequest(
        wake_id="wake-capacity",
        source="api",
        target_kind="new_run",
        target_run_id=None,
        workload_id="governed-agent-loop",
        occurrence_id="capacity-1",
        deduplication_key="api:capacity-1",
        payload={
            "schema_version": "governed_agent_wake_dispatch.v1",
            "request": request,
            "creation_timestamp_utc": now.isoformat(),
            "decision_timestamps_utc": [
                (now + timedelta(seconds=1)).isoformat(),
                (now + timedelta(seconds=2)).isoformat(),
            ],
            "next_lease_expiries_utc": [(now + timedelta(seconds=20)).isoformat()],
        },
        created_at_utc=now.isoformat(),
    )
