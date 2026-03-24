# Layer: integration

from __future__ import annotations

from pathlib import Path

import pytest

from orket.adapters.storage.async_control_plane_record_repository import (
    AsyncControlPlaneRecordRepository,
    ControlPlaneRecordConflictError,
)
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import CheckpointRecord
from orket.core.domain import (
    AuthoritySourceClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ClosureBasisClassification,
    CompletionClassification,
    DegradationClassification,
    DivergenceClass,
    EvidenceSufficiencyClassification,
    LeaseStatus,
    RecoveryActionClass,
    ResidualUncertaintyClassification,
    ResultClass,
    SafeContinuationClass,
    SideEffectBoundaryClass,
)


pytestmark = pytest.mark.integration


def _checkpoint() -> CheckpointRecord:
    return CheckpointRecord(
        checkpoint_id="checkpoint-1",
        parent_ref="attempt-1",
        creation_timestamp="2026-03-23T01:20:00+00:00",
        state_snapshot_ref="snapshot-1",
        resumability_class=CheckpointResumabilityClass.RESUME_NEW_ATTEMPT_FROM_CHECKPOINT,
        invalidation_conditions=["policy_digest_mismatch"],
        dependent_resource_ids=["resource:sb-1"],
        dependent_effect_refs=["effect-1"],
        policy_digest="sha256:policy-1",
        integrity_verification_ref="integrity-checkpoint-1",
    )


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_persists_publication_flow(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)
    checkpoint = _checkpoint()

    journal_entry = await service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T01:21:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )
    checkpoint_acceptance = await service.accept_checkpoint(
        acceptance_id="accept-1",
        checkpoint=checkpoint,
        supervisor_authority_ref="supervisor-1",
        decision_timestamp="2026-03-23T01:22:00+00:00",
        required_reobservation_class=CheckpointReobservationClass.TARGET_ONLY,
        integrity_verification_ref="integrity-checkpoint-1",
        journal_entries=[journal_entry],
    )
    decision = await service.publish_recovery_decision(
        decision_id="rd-1",
        run_id="run-1",
        failed_attempt_id="attempt-1",
        failure_classification_basis="tool_timeout",
        side_effect_boundary_class=SideEffectBoundaryClass.PRE_EFFECT_FAILURE,
        recovery_policy_ref="policy-1",
        authorized_next_action=RecoveryActionClass.RESUME_FROM_CHECKPOINT,
        rationale_ref="recovery-receipt-1",
        target_checkpoint_id="checkpoint-1",
        new_attempt_id="attempt-2",
    )
    lease = await service.publish_lease(
        lease_id="sandbox-lease:sb-1",
        resource_id="sandbox-scope:sb-1",
        holder_ref="sandbox-instance:runner-a",
        lease_epoch=1,
        publication_timestamp="2026-03-23T01:22:15+00:00",
        expiry_basis="sandbox_lifecycle_policy:docker_sandbox_lifecycle.v1;expires_at=2026-03-23T01:27:15+00:00",
        status=LeaseStatus.ACTIVE,
        last_confirmed_observation="sandbox-lifecycle:sb-1:active:2",
        cleanup_eligibility_rule="sandbox_cleanup_policy:docker_sandbox_lifecycle.v1",
    )
    reconciliation = await service.publish_reconciliation(
        reconciliation_id="recon-1",
        target_ref="run-1",
        comparison_scope="run_scope",
        observed_refs=["obs-1"],
        intended_refs=["intent-1"],
        divergence_class=DivergenceClass.RESOURCE_STATE_DIVERGED,
        residual_uncertainty_classification=ResidualUncertaintyClassification.UNRESOLVED,
        publication_timestamp="2026-03-23T01:22:30+00:00",
        safe_continuation_class=SafeContinuationClass.TERMINAL_WITHOUT_CLEANUP,
    )
    final_truth = await service.publish_final_truth(
        final_truth_record_id="truth-1",
        run_id="run-1",
        result_class=ResultClass.DEGRADED,
        completion_classification=CompletionClassification.PARTIAL,
        evidence_sufficiency_classification=EvidenceSufficiencyClassification.SUFFICIENT,
        residual_uncertainty_classification=ResidualUncertaintyClassification.BOUNDED,
        degradation_classification=DegradationClassification.DECLARED,
        closure_basis=ClosureBasisClassification.RECONCILIATION_CLOSED,
        authority_sources=[
            AuthoritySourceClass.RECONCILIATION_RECORD,
            AuthoritySourceClass.RECEIPT_EVIDENCE,
        ],
    )

    listed_entries = await repository.list_effect_journal_entries(run_id="run-1")
    loaded_acceptance = await repository.get_checkpoint_acceptance(checkpoint_id="checkpoint-1")
    loaded_decision = await repository.get_recovery_decision(decision_id="rd-1")
    loaded_lease = await repository.get_latest_lease_record(lease_id="sandbox-lease:sb-1")
    loaded_reconciliation = await repository.get_reconciliation_record(reconciliation_id="recon-1")
    loaded_truth = await repository.get_final_truth(run_id="run-1")

    assert [entry.journal_entry_id for entry in listed_entries] == ["journal-1"]
    assert checkpoint_acceptance.acceptance_id == loaded_acceptance.acceptance_id
    assert decision.decision_id == loaded_decision.decision_id
    assert lease.publication_timestamp == loaded_lease.publication_timestamp
    assert reconciliation.reconciliation_id == loaded_reconciliation.reconciliation_id
    assert final_truth.final_truth_record_id == loaded_truth.final_truth_record_id


@pytest.mark.asyncio
async def test_async_control_plane_record_repository_rejects_conflicting_record_id_reuse(tmp_path: Path) -> None:
    repository = AsyncControlPlaneRecordRepository(tmp_path / "control_plane.sqlite3")
    service = ControlPlanePublicationService(repository=repository)

    await service.append_effect_journal_entry(
        journal_entry_id="journal-1",
        effect_id="effect-1",
        run_id="run-1",
        attempt_id="attempt-1",
        step_id="step-1",
        authorization_basis_ref="auth-1",
        publication_timestamp="2026-03-23T01:23:00+00:00",
        intended_target_ref="resource:sb-1",
        observed_result_ref="receipt-1",
        uncertainty_classification=ResidualUncertaintyClassification.NONE,
        integrity_verification_ref="integrity-1",
    )

    with pytest.raises(ControlPlaneRecordConflictError, match="reused with different payload"):
        await service.append_effect_journal_entry(
            journal_entry_id="journal-1",
            effect_id="effect-2",
            run_id="run-1",
            attempt_id="attempt-1",
            step_id="step-2",
            authorization_basis_ref="auth-2",
            publication_timestamp="2026-03-23T01:24:00+00:00",
            intended_target_ref="resource:sb-2",
            observed_result_ref="receipt-2",
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref="integrity-2",
        )
