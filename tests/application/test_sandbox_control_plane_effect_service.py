# Layer: unit

from __future__ import annotations

import pytest

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.sandbox_control_plane_effect_service import SandboxControlPlaneEffectService
from orket.application.services.sandbox_control_plane_execution_service import SandboxControlPlaneExecutionService
from orket.application.services.sandbox_lifecycle_policy import SandboxLifecyclePolicy
from orket.core.contracts import AttemptRecord, RunRecord, StepRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository, ControlPlaneRecordRepository
from orket.core.domain import ResidualUncertaintyClassification
from orket.core.domain.sandbox_lifecycle import TerminalReason
from tests.application.test_control_plane_publication_service import InMemoryControlPlaneRecordRepository


pytestmark = pytest.mark.unit


class InMemoryControlPlaneExecutionRepository(ControlPlaneExecutionRepository):
    def __init__(self) -> None:
        self.run_by_id: dict[str, RunRecord] = {}
        self.attempt_by_id: dict[str, AttemptRecord] = {}
        self.step_by_id: dict[str, StepRecord] = {}

    async def save_run_record(self, *, record: RunRecord) -> RunRecord:
        self.run_by_id[record.run_id] = record
        return record

    async def get_run_record(self, *, run_id: str) -> RunRecord | None:
        return self.run_by_id.get(run_id)

    async def save_attempt_record(self, *, record: AttemptRecord) -> AttemptRecord:
        self.attempt_by_id[record.attempt_id] = record
        return record

    async def get_attempt_record(self, *, attempt_id: str) -> AttemptRecord | None:
        return self.attempt_by_id.get(attempt_id)

    async def list_attempt_records(self, *, run_id: str) -> list[AttemptRecord]:
        return sorted(
            [record for record in self.attempt_by_id.values() if record.run_id == run_id],
            key=lambda item: item.attempt_ordinal,
        )

    async def save_step_record(self, *, record: StepRecord) -> StepRecord:
        self.step_by_id[record.step_id] = record
        return record

    async def get_step_record(self, *, step_id: str) -> StepRecord | None:
        return self.step_by_id.get(step_id)

    async def list_step_records(self, *, attempt_id: str) -> list[StepRecord]:
        return sorted(
            [record for record in self.step_by_id.values() if record.attempt_id == attempt_id],
            key=lambda item: item.step_id,
        )


@pytest.mark.asyncio
async def test_effect_service_publishes_deploy_and_cleanup_entries_in_order() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=publication_repo)
    execution = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=publication,
    )
    service = SandboxControlPlaneEffectService(
        publication=publication,
        execution_repository=execution_repo,
    )

    await execution.initialize_execution(
        sandbox_id="sb-1",
        run_id="run-1",
        workload_id="sandbox-workload:fastapi-react-postgres",
        workload_version="docker_sandbox_runtime.v1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-24T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-1",
        policy=SandboxLifecyclePolicy(),
    )

    deploy = await service.publish_deploy_effect(
        sandbox_id="sb-1",
        run_id="run-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        observed_at="2026-03-24T00:01:00+00:00",
        lease_epoch=1,
    )
    await execution.finalize_terminal_execution(
        run_id="run-1",
        observed_at="2026-03-24T00:03:00+00:00",
        terminal_reason=TerminalReason.CANCELED,
        policy_version="docker_sandbox_lifecycle.v1",
        final_truth_record_id="truth-1",
        rationale_ref="evidence-1",
    )
    cleanup = await service.publish_cleanup_effect(
        sandbox_id="sb-1",
        run_id="run-1",
        compose_project="orket-sandbox-sb-1",
        workspace_path="workspace/sb-1",
        observed_at="2026-03-24T00:04:00+00:00",
        lease_epoch=1,
        cleanup_result="verified_complete",
    )

    entries = await publication_repo.list_effect_journal_entries(run_id="run-1")

    assert [entry.effect_id for entry in entries] == [
        "sandbox-effect:sb-1:deploy:lease_epoch:00000001",
        "sandbox-effect:sb-1:cleanup:lease_epoch:00000001",
    ]
    assert deploy.publication_sequence == 1
    assert cleanup.publication_sequence == 2
    assert cleanup.prior_journal_entry_id == deploy.journal_entry_id
    assert cleanup.uncertainty_classification is ResidualUncertaintyClassification.NONE


@pytest.mark.asyncio
async def test_effect_service_is_idempotent_for_duplicate_deploy_publication() -> None:
    execution_repo = InMemoryControlPlaneExecutionRepository()
    publication_repo: ControlPlaneRecordRepository = InMemoryControlPlaneRecordRepository()
    publication = ControlPlanePublicationService(repository=publication_repo)
    execution = SandboxControlPlaneExecutionService(
        repository=execution_repo,
        publication=publication,
    )
    service = SandboxControlPlaneEffectService(
        publication=publication,
        execution_repository=execution_repo,
    )

    await execution.initialize_execution(
        sandbox_id="sb-2",
        run_id="run-2",
        workload_id="sandbox-workload:fastapi-react-postgres",
        workload_version="docker_sandbox_runtime.v1",
        compose_project="orket-sandbox-sb-2",
        workspace_path="workspace/sb-2",
        configuration_payload={"tech_stack": "fastapi-react-postgres"},
        creation_timestamp="2026-03-24T00:00:00+00:00",
        admission_decision_receipt_ref="sandbox-reservation:sb-2",
        policy=SandboxLifecyclePolicy(),
    )

    first = await service.publish_deploy_effect(
        sandbox_id="sb-2",
        run_id="run-2",
        compose_project="orket-sandbox-sb-2",
        workspace_path="workspace/sb-2",
        observed_at="2026-03-24T00:01:00+00:00",
        lease_epoch=1,
    )
    second = await service.publish_deploy_effect(
        sandbox_id="sb-2",
        run_id="run-2",
        compose_project="orket-sandbox-sb-2",
        workspace_path="workspace/sb-2",
        observed_at="2026-03-24T00:02:00+00:00",
        lease_epoch=1,
    )

    entries = await publication_repo.list_effect_journal_entries(run_id="run-2")

    assert first.journal_entry_id == second.journal_entry_id
    assert len(entries) == 1
