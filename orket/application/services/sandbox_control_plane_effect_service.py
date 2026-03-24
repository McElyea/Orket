from __future__ import annotations

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.core.contracts import AttemptRecord, EffectJournalEntryRecord, RunRecord
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import ResidualUncertaintyClassification


class SandboxControlPlaneEffectError(ValueError):
    """Raised when sandbox effect truth cannot be published honestly."""


class SandboxControlPlaneEffectService:
    """Publishes sandbox deploy and cleanup effects into the control-plane journal."""

    def __init__(
        self,
        *,
        publication: ControlPlanePublicationService,
        execution_repository: ControlPlaneExecutionRepository,
    ) -> None:
        self.publication = publication
        self.execution_repository = execution_repository

    async def publish_deploy_effect(
        self,
        *,
        sandbox_id: str,
        run_id: str,
        compose_project: str,
        workspace_path: str,
        observed_at: str,
        lease_epoch: int,
    ) -> EffectJournalEntryRecord:
        run, attempt = await self._require_run_and_attempt(run_id=run_id)
        effect_id = self._effect_id(sandbox_id=sandbox_id, effect_kind="deploy", lease_epoch=lease_epoch)
        existing = await self._existing_entry(run_id=run_id, effect_id=effect_id)
        if existing is not None:
            return existing
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=self._journal_entry_id(
                sandbox_id=sandbox_id,
                effect_kind="deploy",
                lease_epoch=lease_epoch,
            ),
            effect_id=effect_id,
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=self._step_id(
                sandbox_id=sandbox_id,
                effect_kind="deploy",
                lease_epoch=lease_epoch,
            ),
            authorization_basis_ref=self._deploy_authorization_basis(
                run=run,
                lease_epoch=lease_epoch,
            ),
            publication_timestamp=observed_at,
            intended_target_ref=f"sandbox-runtime:{compose_project}",
            observed_result_ref=(
                f"sandbox-deploy-observation:{sandbox_id}:{observed_at}:"
                f"{self._workspace_token(workspace_path)}"
            ),
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=f"sandbox-health-verification:{sandbox_id}:{observed_at}",
        )

    async def publish_cleanup_effect(
        self,
        *,
        sandbox_id: str,
        run_id: str,
        compose_project: str,
        workspace_path: str,
        observed_at: str,
        lease_epoch: int,
        cleanup_result: str,
    ) -> EffectJournalEntryRecord:
        run, attempt = await self._require_run_and_attempt(run_id=run_id)
        effect_id = self._effect_id(sandbox_id=sandbox_id, effect_kind="cleanup", lease_epoch=lease_epoch)
        existing = await self._existing_entry(run_id=run_id, effect_id=effect_id)
        if existing is not None:
            return existing
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=self._journal_entry_id(
                sandbox_id=sandbox_id,
                effect_kind="cleanup",
                lease_epoch=lease_epoch,
            ),
            effect_id=effect_id,
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=self._step_id(
                sandbox_id=sandbox_id,
                effect_kind="cleanup",
                lease_epoch=lease_epoch,
            ),
            authorization_basis_ref=(
                f"sandbox-cleanup-authority:{sandbox_id}:lease_epoch:{lease_epoch:08d}"
            ),
            publication_timestamp=observed_at,
            intended_target_ref=f"sandbox-runtime:{compose_project}",
            observed_result_ref=(
                f"sandbox-cleanup-verification:{sandbox_id}:{cleanup_result}:{observed_at}:"
                f"{self._workspace_token(workspace_path)}"
            ),
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=f"sandbox-cleanup-verification:{sandbox_id}:{observed_at}",
        )

    async def _require_run_and_attempt(self, *, run_id: str) -> tuple[RunRecord, AttemptRecord]:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise SandboxControlPlaneEffectError(f"control-plane run not found for {run_id}")
        attempt = None
        if run.current_attempt_id is not None:
            attempt = await self.execution_repository.get_attempt_record(attempt_id=run.current_attempt_id)
        if attempt is None:
            attempts = await self.execution_repository.list_attempt_records(run_id=run_id)
            if attempts:
                attempt = attempts[-1]
        if attempt is None:
            raise SandboxControlPlaneEffectError(f"control-plane attempt not found for {run_id}")
        return run, attempt

    async def _existing_entry(
        self,
        *,
        run_id: str,
        effect_id: str,
    ) -> EffectJournalEntryRecord | None:
        entries = await self.publication.repository.list_effect_journal_entries(run_id=run_id)
        for entry in entries:
            if entry.effect_id == effect_id:
                return entry
        return None

    @staticmethod
    def _deploy_authorization_basis(*, run: RunRecord, lease_epoch: int) -> str:
        if lease_epoch == 1:
            return run.admission_decision_receipt_ref
        return f"sandbox-recovery:{run.run_id}:reacquire:{lease_epoch:08d}"

    @staticmethod
    def _effect_id(*, sandbox_id: str, effect_kind: str, lease_epoch: int) -> str:
        return f"sandbox-effect:{sandbox_id}:{effect_kind}:lease_epoch:{lease_epoch:08d}"

    @staticmethod
    def _journal_entry_id(*, sandbox_id: str, effect_kind: str, lease_epoch: int) -> str:
        return f"sandbox-journal:{sandbox_id}:{effect_kind}:lease_epoch:{lease_epoch:08d}"

    @staticmethod
    def _step_id(*, sandbox_id: str, effect_kind: str, lease_epoch: int) -> str:
        return f"sandbox-step:{sandbox_id}:{effect_kind}:lease_epoch:{lease_epoch:08d}"

    @staticmethod
    def _workspace_token(workspace_path: str) -> str:
        token = str(workspace_path).replace("\\", "/").strip("/")
        return token or "workspace-root"


__all__ = [
    "SandboxControlPlaneEffectError",
    "SandboxControlPlaneEffectService",
]
