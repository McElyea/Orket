# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_closure_service import (
    SandboxControlPlaneClosureError,
    SandboxControlPlaneClosureService,
)
from orket.core.contracts import (
    CheckpointAcceptanceRecord,
    EffectJournalEntryRecord,
    FinalTruthRecord,
    LeaseRecord,
    ReconciliationRecord,
    RecoveryDecisionRecord,
)
from orket.core.contracts.repositories import ControlPlaneRecordRepository
from orket.core.domain import (
    ClosureBasisClassification,
    DivergenceClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
)
from orket.core.domain.sandbox_lifecycle import CleanupState, SandboxState, TerminalReason
from orket.core.domain.sandbox_lifecycle_records import ManagedResourceInventory, SandboxLifecycleRecord


pytestmark = pytest.mark.unit


class FinalTruthOnlyRepository(ControlPlaneRecordRepository):
    def __init__(self) -> None:
        self.final_truth_by_run: dict[str, FinalTruthRecord] = {}

    async def append_effect_journal_entry(
        self,
        *,
        run_id: str,
        entry: EffectJournalEntryRecord,
    ) -> EffectJournalEntryRecord:
        raise NotImplementedError

    async def list_effect_journal_entries(self, *, run_id: str) -> list[EffectJournalEntryRecord]:
        raise NotImplementedError

    async def save_checkpoint_acceptance(
        self,
        *,
        acceptance: CheckpointAcceptanceRecord,
    ) -> CheckpointAcceptanceRecord:
        raise NotImplementedError

    async def get_checkpoint_acceptance(
        self,
        *,
        checkpoint_id: str,
    ) -> CheckpointAcceptanceRecord | None:
        raise NotImplementedError

    async def save_recovery_decision(
        self,
        *,
        decision: RecoveryDecisionRecord,
    ) -> RecoveryDecisionRecord:
        raise NotImplementedError

    async def get_recovery_decision(self, *, decision_id: str) -> RecoveryDecisionRecord | None:
        raise NotImplementedError

    async def append_lease_record(
        self,
        *,
        record: LeaseRecord,
    ) -> LeaseRecord:
        raise NotImplementedError

    async def list_lease_records(self, *, lease_id: str) -> list[LeaseRecord]:
        raise NotImplementedError

    async def get_latest_lease_record(self, *, lease_id: str) -> LeaseRecord | None:
        raise NotImplementedError

    async def save_reconciliation_record(
        self,
        *,
        record: ReconciliationRecord,
    ) -> ReconciliationRecord:
        raise NotImplementedError

    async def get_reconciliation_record(self, *, reconciliation_id: str) -> ReconciliationRecord | None:
        raise NotImplementedError

    async def save_final_truth(self, *, record: FinalTruthRecord) -> FinalTruthRecord:
        self.final_truth_by_run[record.run_id] = record
        return record

    async def get_final_truth(self, *, run_id: str) -> FinalTruthRecord | None:
        return self.final_truth_by_run.get(run_id)


def _terminal_record(*, terminal_reason: TerminalReason) -> SandboxLifecycleRecord:
    return SandboxLifecycleRecord(
        sandbox_id="sb-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        run_id="run-1",
        owner_instance_id="runner-a",
        lease_epoch=1,
        lease_expires_at="2026-03-23T01:05:00+00:00",
        state=SandboxState.TERMINAL,
        cleanup_state=CleanupState.NONE,
        record_version=4,
        created_at="2026-03-23T01:00:00+00:00",
        last_heartbeat_at="2026-03-23T01:00:30+00:00",
        terminal_at="2026-03-23T01:02:00+00:00",
        terminal_reason=terminal_reason,
        cleanup_due_at="2026-03-23T01:12:00+00:00",
        cleanup_attempts=0,
        required_evidence_ref="evidence/sb-1.json",
        managed_resource_inventory=ManagedResourceInventory(),
        requires_reconciliation=False,
        docker_context="desktop-linux",
        docker_host_id="host-a",
    )


def _reconciliation() -> ReconciliationRecord:
    return ReconciliationRecord(
        reconciliation_id="recon-1",
        target_ref="run-1",
        comparison_scope="run_scope",
        observed_refs=["obs-1"],
        intended_refs=["intent-1"],
        divergence_class=DivergenceClass.RESOURCE_STATE_DIVERGED,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp="2026-03-23T01:03:00+00:00",
        safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
    )


@pytest.mark.asyncio
async def test_sandbox_control_plane_closure_service_publishes_success_final_truth() -> None:
    repository = FinalTruthOnlyRepository()
    service = SandboxControlPlaneClosureService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    truth = await service.publish_terminal_final_truth(record=_terminal_record(terminal_reason=TerminalReason.SUCCESS))

    assert truth.result_class is ResultClass.SUCCESS
    assert truth.closure_basis is ClosureBasisClassification.NORMAL_EXECUTION
    assert (await repository.get_final_truth(run_id="run-1")) is not None


@pytest.mark.asyncio
async def test_sandbox_control_plane_closure_service_maps_policy_terminal_reason() -> None:
    repository = FinalTruthOnlyRepository()
    service = SandboxControlPlaneClosureService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    truth = await service.publish_terminal_final_truth(record=_terminal_record(terminal_reason=TerminalReason.HARD_MAX_AGE))

    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.POLICY_TERMINAL_STOP


@pytest.mark.asyncio
async def test_sandbox_control_plane_closure_service_rejects_unsupported_reason() -> None:
    repository = FinalTruthOnlyRepository()
    service = SandboxControlPlaneClosureService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    with pytest.raises(SandboxControlPlaneClosureError, match="requires reconciliation_record"):
        await service.publish_terminal_final_truth(record=_terminal_record(terminal_reason=TerminalReason.LOST_RUNTIME))


@pytest.mark.asyncio
async def test_sandbox_control_plane_closure_service_accepts_lost_runtime_with_reconciliation() -> None:
    repository = FinalTruthOnlyRepository()
    service = SandboxControlPlaneClosureService(
        publication=ControlPlanePublicationService(repository=repository)
    )

    truth = await service.publish_terminal_final_truth(
        record=_terminal_record(terminal_reason=TerminalReason.LOST_RUNTIME),
        reconciliation_record=_reconciliation(),
    )

    assert truth.result_class is ResultClass.BLOCKED
    assert truth.closure_basis is ClosureBasisClassification.RECONCILIATION_CLOSED
