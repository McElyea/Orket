from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

from orket.adapters.storage.async_control_plane_execution_repository import AsyncControlPlaneExecutionRepository
from orket.adapters.storage.async_control_plane_record_repository import AsyncControlPlaneRecordRepository
from orket.adapters.storage.control_plane_transaction import SQLiteControlPlaneTransactions
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.application.services.control_plane_workload_catalog import (
    GITEA_STATE_WORKER_EXECUTION_WORKLOAD,
)
from orket.application.services.gitea_state_control_plane_closeout import publish_gitea_closeout
from orket.application.services.gitea_state_control_plane_lease_service import GiteaStateControlPlaneLeaseService
from orket.application.services.runtime_input_service import RuntimeInputService
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, FinalTruthRecord, RunRecord, StepRecord
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    CapabilityClass,
    ResidualUncertaintyClassification,
    RunState,
)
from orket.runtime_paths import resolve_control_plane_db_path


class GiteaStateControlPlaneExecutionError(ValueError):
    """Raised when Gitea worker execution authority cannot be published truthfully."""


class GiteaStateControlPlaneExecutionService:
    """Publishes lease-backed Gitea worker execution into first-class control-plane records."""

    WORKLOAD = GITEA_STATE_WORKER_EXECUTION_WORKLOAD

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
        transactions: ControlPlaneTransactionFactory,
        now_utc: Callable[[], str] | None = None,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication
        self.transactions = transactions
        self.now_utc = now_utc or RuntimeInputService().utc_now_iso

    async def begin_claimed_execution(
        self,
        *,
        card_id: str,
        worker_id: str,
        from_state: str,
        success_state: str,
        failure_state: str,
        lease_observation: Mapping[str, object],
    ) -> tuple[RunRecord, AttemptRecord]:
        lease_epoch = self._lease_epoch(lease_observation)
        run_id = self.run_id_for(card_id=card_id, lease_epoch=lease_epoch)
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is not None:
            attempt = await self.execution_repository.get_attempt_record(
                attempt_id=self.attempt_id_for(run_id=run_id)
            )
            if attempt is None:
                raise GiteaStateControlPlaneExecutionError(f"gitea run missing attempt: {run_id}")
            return existing_run, attempt

        creation_timestamp = str(self._lease_payload(lease_observation).get("acquired_at") or self.now_utc())
        policy_payload = {
            "success_state": str(success_state),
            "failure_state": str(failure_state),
            "lease_epoch": lease_epoch,
        }
        configuration_payload = {
            "card_id": str(card_id),
            "worker_id": str(worker_id),
            "from_state": str(from_state),
            "success_state": str(success_state),
            "failure_state": str(failure_state),
            "lease_observation": dict(lease_observation),
        }
        run = RunRecord(
            run_id=run_id,
            workload_id=self.WORKLOAD.workload_id,
            workload_version=self.WORKLOAD.workload_version,
            policy_snapshot_id=f"gitea-state-worker-policy:{card_id}",
            policy_digest=snapshot_digest(policy_payload),
            configuration_snapshot_id=f"gitea-state-worker-config:{run_id}",
            configuration_digest=snapshot_digest(configuration_payload),
            creation_timestamp=creation_timestamp,
            admission_decision_receipt_ref=self.lease_observation_ref(card_id=card_id, lease_observation=lease_observation),
            namespace_scope=self.namespace_scope_for(card_id=card_id),
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=self.attempt_id_for(run_id=run_id),
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[run.admission_decision_receipt_ref],
            configuration_payload=configuration_payload,
            configuration_source_refs=[run.admission_decision_receipt_ref],
        )
        attempt = AttemptRecord(
            attempt_id=self.attempt_id_for(run_id=run_id),
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=self.snapshot_ref(card_id=card_id, from_state=from_state, lease_observation=lease_observation),
            start_timestamp=creation_timestamp,
        )
        run = await self.execution_repository.save_run_record(record=run)
        attempt = await self.execution_repository.save_attempt_record(record=attempt)
        return run, attempt

    async def publish_claim_transition(
        self,
        *,
        run_id: str,
        attempt_id: str,
        card_id: str,
        from_state: str,
        to_state: str,
    ) -> tuple[StepRecord, EffectJournalEntryRecord]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=attempt_id)
        step_id = self.step_id_for(run_id=run_id, stage="claim")
        existing_step = await self.execution_repository.get_step_record(step_id=step_id)
        if existing_step is None:
            existing_step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=step_id,
                    attempt_id=attempt.attempt_id,
                    step_kind="gitea_state_transition",
                    namespace_scope=run.namespace_scope,
                    input_ref=attempt.starting_state_snapshot_ref,
                    output_ref=self.transition_result_ref(
                        card_id=card_id,
                        lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                        from_state=from_state,
                        to_state=to_state,
                    ),
                    capability_used=CapabilityClass.EXTERNAL_MUTATION,
                    resources_touched=self._resources_touched(card_id=card_id),
                    observed_result_classification="state_transition_succeeded",
                    receipt_refs=[
                        attempt.starting_state_snapshot_ref,
                        self.transition_result_ref(
                            card_id=card_id,
                            lease_epoch=self.lease_epoch_for_run(run_id=run_id),
                            from_state=from_state,
                            to_state=to_state,
                        ),
                    ],
                    closure_classification="step_completed",
                )
            )
        effect = await self._ensure_effect(
            run=run,
            attempt=attempt,
            step=existing_step,
            stage="claim",
            card_id=card_id,
        )
        return existing_step, effect

    async def publish_release_transition_and_finalize(
        self, *, run_id: str, attempt_id: str, card_id: str, final_state: str,
        error: str | None, success_state: str, worker_id: str,
        lease_observation: Mapping[str, object], lease_expired: bool,
        lease_service: GiteaStateControlPlaneLeaseService,
    ) -> tuple[RunRecord, AttemptRecord, StepRecord, EffectJournalEntryRecord, FinalTruthRecord]:
        async with self.transactions() as transaction:
            publication = ControlPlanePublicationService(
                repository=transaction.records, authority=self.publication.authority,
            )
            scoped = GiteaStateControlPlaneExecutionService(
                execution_repository=transaction.execution, publication=publication,
                transactions=self.transactions, now_utc=self.now_utc,
            )
            leases = GiteaStateControlPlaneLeaseService(publication=publication, now_utc=lease_service.now_utc)
            return await publish_gitea_closeout(
                scoped, leases, run_id=run_id, attempt_id=attempt_id, card_id=card_id,
                final_state=final_state, error=error, success_state=success_state,
                worker_id=worker_id, lease_observation=lease_observation, lease_expired=lease_expired,
            )

    @staticmethod
    def run_id_for(*, card_id: str, lease_epoch: int) -> str:
        return f"gitea-state-run:{str(card_id).strip()}:lease_epoch:{int(lease_epoch):08d}"

    @staticmethod
    def attempt_id_for(*, run_id: str) -> str:
        return f"{run_id}:attempt:0001"

    @staticmethod
    def step_id_for(*, run_id: str, stage: str) -> str:
        return f"{run_id}:step:{str(stage).strip()}"

    @staticmethod
    def effect_id_for(*, run_id: str, stage: str) -> str:
        return f"gitea-state-effect:{run_id}:{str(stage).strip()}"

    @staticmethod
    def namespace_scope_for(*, card_id: str) -> str:
        return f"issue:{str(card_id).strip()}"

    @classmethod
    def lease_epoch_for_run(cls, *, run_id: str) -> int:
        marker = ":lease_epoch:"
        if marker not in run_id:
            raise GiteaStateControlPlaneExecutionError(f"run_id missing lease epoch: {run_id}")
        return int(run_id.rsplit(marker, 1)[-1])

    @classmethod
    def lease_observation_ref(cls, *, card_id: str, lease_observation: Mapping[str, object]) -> str:
        version = lease_observation.get("version")
        if version is not None:
            return f"gitea-card-snapshot:{str(card_id).strip()}:version:{cls._required_int(version)}"
        return f"gitea-card-lease-observation:{str(card_id).strip()}:epoch:{cls._lease_epoch(lease_observation):08d}"

    @classmethod
    def snapshot_ref(cls, *, card_id: str, from_state: str, lease_observation: Mapping[str, object]) -> str:
        observation_ref = cls.lease_observation_ref(card_id=card_id, lease_observation=lease_observation)
        return f"{observation_ref}:state:{str(from_state).strip() or 'ready'}"

    @staticmethod
    def transition_result_ref(*, card_id: str, lease_epoch: int, from_state: str, to_state: str) -> str:
        return (
            f"gitea-card-transition:{str(card_id).strip()}"
            f":lease_epoch:{int(lease_epoch):08d}"
            f":{str(from_state).strip() or 'unknown'}->{str(to_state).strip() or 'unknown'}"
        )

    async def _ensure_effect(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        step: StepRecord,
        stage: str,
        card_id: str,
    ) -> EffectJournalEntryRecord:
        existing = await self._existing_effect(run_id=run.run_id, stage=stage)
        if existing is not None:
            return existing
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=f"gitea-state-journal:{run.run_id}:{stage}",
            effect_id=self.effect_id_for(run_id=run.run_id, stage=stage),
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=run.admission_decision_receipt_ref,
            publication_timestamp=self.now_utc(),
            intended_target_ref=f"gitea-card:{str(card_id).strip()}",
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or run.admission_decision_receipt_ref,
        )

    async def _existing_effect(self, *, run_id: str, stage: str) -> EffectJournalEntryRecord | None:
        effect_id = self.effect_id_for(run_id=run_id, stage=stage)
        entries = await self.publication.repository.list_effect_journal_entries(run_id=run_id)
        for entry in entries:
            if entry.effect_id == effect_id:
                return entry
        return None

    async def _require_effect(self, *, run_id: str, stage: str) -> EffectJournalEntryRecord:
        effect = await self._existing_effect(run_id=run_id, stage=stage)
        if effect is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea run missing effect journal entry: {run_id}:{stage}")
        return effect

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea worker run not found: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str) -> AttemptRecord:
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if attempt is None:
            raise GiteaStateControlPlaneExecutionError(f"gitea worker attempt not found: {attempt_id}")
        return attempt

    @staticmethod
    def _resources_touched(*, card_id: str) -> list[str]:
        normalized_card_id = str(card_id).strip()
        namespace_scope = GiteaStateControlPlaneExecutionService.namespace_scope_for(card_id=normalized_card_id)
        return [f"gitea-card:{normalized_card_id}", f"issue:{normalized_card_id}", f"namespace:{namespace_scope}"]

    @staticmethod
    def _lease_payload(lease_observation: Mapping[str, object]) -> Mapping[str, object]:
        nested = lease_observation.get("lease")
        return nested if isinstance(nested, Mapping) else lease_observation

    @classmethod
    def _lease_epoch(cls, lease_observation: Mapping[str, object]) -> int:
        payload = cls._lease_payload(lease_observation)
        raw = payload.get("epoch")
        if raw is None:
            raw = lease_observation.get("lease_epoch")
        try:
            return cls._required_int(raw)
        except (TypeError, ValueError) as exc:
            raise GiteaStateControlPlaneExecutionError("gitea worker execution publication requires lease epoch") from exc

    @staticmethod
    def _required_int(value: object) -> int:
        if not isinstance(value, (str, bytes, bytearray, int, float)):
            raise TypeError("expected integer-like value")
        return int(value)

def build_gitea_state_control_plane_execution_service(
    db_path: str | Path | None = None, *, now_utc: Callable[[], str] | None = None,
) -> GiteaStateControlPlaneExecutionService:
    resolved_db_path = resolve_control_plane_db_path(db_path)
    publication = ControlPlanePublicationService(repository=AsyncControlPlaneRecordRepository(resolved_db_path))
    return GiteaStateControlPlaneExecutionService(
        execution_repository=AsyncControlPlaneExecutionRepository(resolved_db_path),
        publication=publication,
        transactions=SQLiteControlPlaneTransactions(resolved_db_path), now_utc=now_utc,
    )

__all__ = [
    "GiteaStateControlPlaneExecutionError",
    "GiteaStateControlPlaneExecutionService",
    "build_gitea_state_control_plane_execution_service",
]
