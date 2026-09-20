from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.application.services.extension_workload_closeout import finalize_extension_workload
from orket.core.contracts import (
    AttemptRecord,
    CheckpointAcceptanceRecord,
    CheckpointRecord,
    EffectJournalEntryRecord,
    FinalTruthRecord,
    RunRecord,
    StepRecord,
    WorkloadRecord,
)
from orket.core.contracts.control_plane_transaction import ControlPlaneTransactionFactory
from orket.core.contracts.repositories import ControlPlaneExecutionRepository
from orket.core.domain import (
    AttemptState,
    AuthoritySourceClass,
    CapabilityClass,
    CheckpointReobservationClass,
    CheckpointResumabilityClass,
    ResidualUncertaintyClassification,
    ResultClass,
    RunState,
)
from orket.naming import sanitize_name


@dataclass(frozen=True)
class ExtensionWorkloadControlPlaneStart:
    run: RunRecord
    attempt: AttemptRecord
    start_step: StepRecord
    start_effect: EffectJournalEntryRecord
    checkpoint: CheckpointRecord
    checkpoint_acceptance: CheckpointAcceptanceRecord


@dataclass(frozen=True)
class ExtensionWorkloadControlPlaneCloseout:
    run: RunRecord
    attempt: AttemptRecord
    closeout_step: StepRecord
    closeout_effect: EffectJournalEntryRecord
    final_truth: FinalTruthRecord


class ExtensionWorkloadControlPlaneError(ValueError):
    """Raised when extension workload control-plane publication cannot be completed truthfully."""


class ExtensionWorkloadControlPlaneService:
    """Publishes extension workload execution into first-class control-plane records."""

    def __init__(
        self,
        *,
        execution_repository: ControlPlaneExecutionRepository,
        publication: ControlPlanePublicationService,
        transactions: ControlPlaneTransactionFactory,
    ) -> None:
        self.execution_repository = execution_repository
        self.publication = publication
        self.transactions = transactions

    async def begin_execution(
        self,
        *,
        run_id: str,
        extension_id: str,
        control_plane_workload_record: Mapping[str, object],
        policy_payload: Mapping[str, object],
        configuration_payload: Mapping[str, object],
        admission_decision_receipt_ref: str,
        creation_timestamp: str,
    ) -> ExtensionWorkloadControlPlaneStart:
        workload = WorkloadRecord.model_validate(dict(control_plane_workload_record))
        existing_run = await self.execution_repository.get_run_record(run_id=run_id)
        if existing_run is not None:
            raise ExtensionWorkloadControlPlaneError(f"extension workload run already exists: {run_id}")

        run = RunRecord(
            run_id=run_id,
            workload_id=workload.workload_id,
            workload_version=workload.workload_version,
            policy_snapshot_id=self.policy_snapshot_id_for(run_id=run_id),
            policy_digest=snapshot_digest(policy_payload),
            configuration_snapshot_id=self.configuration_snapshot_id_for(run_id=run_id),
            configuration_digest=snapshot_digest(configuration_payload),
            creation_timestamp=creation_timestamp,
            admission_decision_receipt_ref=str(admission_decision_receipt_ref),
            namespace_scope=self.namespace_scope_for(extension_id=extension_id),
            lifecycle_state=RunState.EXECUTING,
            current_attempt_id=self.attempt_id_for(run_id=run_id),
        )
        await publish_run_snapshots(
            publication=self.publication,
            run=run,
            policy_payload=policy_payload,
            policy_source_refs=[run.admission_decision_receipt_ref, workload.workload_digest],
            configuration_payload=configuration_payload,
            configuration_source_refs=[run.admission_decision_receipt_ref],
        )
        attempt = AttemptRecord(
            attempt_id=self.attempt_id_for(run_id=run_id),
            run_id=run_id,
            attempt_ordinal=1,
            attempt_state=AttemptState.EXECUTING,
            starting_state_snapshot_ref=run.configuration_snapshot_id,
            start_timestamp=creation_timestamp,
        )
        run = await self.execution_repository.save_run_record(record=run)
        attempt = await self.execution_repository.save_attempt_record(record=attempt)
        start_step = await self.execution_repository.save_step_record(
            record=StepRecord(
                step_id=self.start_step_id_for(run_id=run_id),
                attempt_id=attempt.attempt_id,
                step_kind="extension_workload_start",
                namespace_scope=run.namespace_scope,
                input_ref=run.admission_decision_receipt_ref,
                output_ref=self.start_result_ref_for(run_id=run_id),
                capability_used=CapabilityClass.DETERMINISTIC_COMPUTE,
                resources_touched=self._run_resources(extension_id=extension_id),
                observed_result_classification="extension_workload_started",
                receipt_refs=[run.admission_decision_receipt_ref, run.configuration_snapshot_id],
                closure_classification="step_completed",
            )
        )
        start_effect = await self._append_effect(
            run=run,
            attempt=attempt,
            step=start_step,
            effect_id=self.effect_id_for(run_id=run_id, stage="start"),
            journal_entry_id=self.journal_entry_id_for(run_id=run_id, stage="start"),
            intended_target_ref=f"extension-workload:{run_id}:lifecycle",
        )
        checkpoint = await self.publication.publish_checkpoint(
            checkpoint=CheckpointRecord(
                checkpoint_id=self.checkpoint_id_for(attempt_id=attempt.attempt_id),
                parent_ref=attempt.attempt_id,
                creation_timestamp=creation_timestamp,
                state_snapshot_ref=run.configuration_snapshot_id,
                resumability_class=CheckpointResumabilityClass.RESUME_FORBIDDEN,
                invalidation_conditions=[
                    "extension_manifest_drift",
                    "extension_input_digest_drift",
                    "extension_namespace_drift",
                ],
                dependent_resource_ids=self._run_resources(extension_id=extension_id),
                dependent_effect_refs=[],
                policy_digest=run.policy_digest,
                integrity_verification_ref=self.checkpoint_integrity_ref(run=run),
            )
        )
        checkpoint_acceptance = await self.publication.accept_checkpoint(
            acceptance_id=self.checkpoint_acceptance_id_for(attempt_id=attempt.attempt_id),
            checkpoint=checkpoint,
            supervisor_authority_ref=f"extension-workload-supervisor:{run.run_id}",
            decision_timestamp=checkpoint.creation_timestamp,
            required_reobservation_class=CheckpointReobservationClass.FULL,
            integrity_verification_ref=checkpoint.integrity_verification_ref,
            journal_entries=[start_effect],
        )
        return ExtensionWorkloadControlPlaneStart(
            run=run,
            attempt=attempt,
            start_step=start_step,
            start_effect=start_effect,
            checkpoint=checkpoint,
            checkpoint_acceptance=checkpoint_acceptance,
        )

    async def publish_sdk_capability_calls(
        self,
        *,
        run_id: str,
        extension_id: str,
        call_records: Sequence[Mapping[str, object]],
    ) -> tuple[tuple[StepRecord, ...], tuple[EffectJournalEntryRecord, ...]]:
        run = await self._require_run(run_id=run_id)
        attempt = await self._require_attempt(attempt_id=run.current_attempt_id)
        previous_ref = self.start_result_ref_for(run_id=run_id)
        steps: list[StepRecord] = []
        effects: list[EffectJournalEntryRecord] = []
        for index, call_record in enumerate(call_records, start=1):
            capability_id = str(call_record.get("capability_id") or "").strip() or "unknown_capability"
            observed_result = str(call_record.get("observed_result") or "").strip() or "unknown"
            step = await self.execution_repository.save_step_record(
                record=StepRecord(
                    step_id=self.capability_step_id_for(run_id=run_id, index=index, capability_id=capability_id),
                    attempt_id=attempt.attempt_id,
                    step_kind="sdk_capability_call",
                    namespace_scope=run.namespace_scope,
                    input_ref=previous_ref,
                    output_ref=self.capability_result_ref_for(
                        run_id=run_id,
                        index=index,
                        capability_id=capability_id,
                        observed_result=observed_result,
                    ),
                    capability_used=self._capability_class_for(capability_id=capability_id),
                    resources_touched=self._capability_resources(extension_id=extension_id, capability_id=capability_id),
                    observed_result_classification=self._capability_observed_result(call_record=call_record),
                    receipt_refs=[
                        self.capability_result_ref_for(
                            run_id=run_id,
                            index=index,
                            capability_id=capability_id,
                            observed_result=observed_result,
                        )
                    ],
                    closure_classification=self._capability_closure_classification(observed_result=observed_result),
                )
            )
            steps.append(step)
            effects.append(
                await self._append_effect(
                    run=run,
                    attempt=attempt,
                    step=step,
                    effect_id=self.capability_effect_id_for(run_id=run_id, index=index, capability_id=capability_id),
                    journal_entry_id=self.capability_journal_entry_id_for(
                        run_id=run_id, index=index, capability_id=capability_id
                    ),
                    intended_target_ref=self._capability_target_ref(
                        extension_id=extension_id,
                        capability_id=capability_id,
                    ),
                )
            )
            previous_ref = step.output_ref or previous_ref
        return tuple(steps), tuple(effects)

    async def finalize_execution(
        self,
        *,
        run_id: str,
        outcome: ResultClass,
        authoritative_result_ref: str,
        authority_sources: list[AuthoritySourceClass],
        prior_step_ref: str,
        failure_class: str = "",
        side_effect_observed: bool = False,
    ) -> ExtensionWorkloadControlPlaneCloseout:
        authority_sources = list(authority_sources)
        async with self.transactions() as transaction:
            owner = ExtensionWorkloadControlPlaneService(
                execution_repository=transaction.execution,
                publication=ControlPlanePublicationService(
                    repository=transaction.records, authority=self.publication.authority),
                transactions=self.transactions,
            )
            values = await finalize_extension_workload(
                owner, run_id=run_id, outcome=outcome, authoritative_result_ref=authoritative_result_ref,
                authority_sources=authority_sources, prior_step_ref=prior_step_ref,
                failure_class=failure_class, side_effect_observed=side_effect_observed,
            )
            return ExtensionWorkloadControlPlaneCloseout(*values)

    @staticmethod
    def namespace_scope_for(*, extension_id: str) -> str:
        return f"extension:{sanitize_name(str(extension_id or 'unknown'))}"

    @staticmethod
    def run_id_for(*, extension_id: str, workload_id: str, creation_timestamp: str, input_identity: str) -> str:
        token = datetime.fromisoformat(creation_timestamp.replace("Z", "+00:00")).astimezone(UTC).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        return (
            f"extension-workload-run:{sanitize_name(extension_id)}:{sanitize_name(workload_id)}:"
            f"{token}:{sanitize_name(input_identity)[:12] or 'input'}"
        )

    @staticmethod
    def attempt_id_for(*, run_id: str) -> str:
        return f"{run_id}:attempt:0001"

    @staticmethod
    def policy_snapshot_id_for(*, run_id: str) -> str:
        return f"{run_id}:policy"

    @staticmethod
    def configuration_snapshot_id_for(*, run_id: str) -> str:
        return f"{run_id}:configuration"

    @staticmethod
    def start_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:start"

    @staticmethod
    def closeout_step_id_for(*, run_id: str) -> str:
        return f"{run_id}:step:closeout"

    @staticmethod
    def start_result_ref_for(*, run_id: str) -> str:
        return f"{run_id}:start"

    @staticmethod
    def effect_id_for(*, run_id: str, stage: str) -> str:
        return f"extension-workload-effect:{run_id}:{sanitize_name(stage)}"

    @staticmethod
    def journal_entry_id_for(*, run_id: str, stage: str) -> str:
        return f"extension-workload-journal:{run_id}:{sanitize_name(stage)}"

    @staticmethod
    def capability_step_id_for(*, run_id: str, index: int, capability_id: str) -> str:
        return f"{run_id}:step:capability:{index:04d}:{sanitize_name(capability_id)}"

    @staticmethod
    def capability_effect_id_for(*, run_id: str, index: int, capability_id: str) -> str:
        return f"extension-workload-effect:{run_id}:capability:{index:04d}:{sanitize_name(capability_id)}"

    @staticmethod
    def capability_journal_entry_id_for(*, run_id: str, index: int, capability_id: str) -> str:
        return f"extension-workload-journal:{run_id}:capability:{index:04d}:{sanitize_name(capability_id)}"

    @staticmethod
    def capability_result_ref_for(*, run_id: str, index: int, capability_id: str, observed_result: str) -> str:
        return (
            f"{run_id}:capability:{index:04d}:{sanitize_name(capability_id)}:"
            f"{sanitize_name(observed_result or 'unknown')}"
        )

    @staticmethod
    def checkpoint_id_for(*, attempt_id: str) -> str:
        return f"extension-workload-checkpoint:{attempt_id}"

    @staticmethod
    def checkpoint_acceptance_id_for(*, attempt_id: str) -> str:
        return f"extension-workload-checkpoint-acceptance:{attempt_id}"

    @staticmethod
    def final_truth_id_for(*, run_id: str) -> str:
        return f"{run_id}:final_truth"

    @staticmethod
    def checkpoint_integrity_ref(*, run: RunRecord) -> str:
        raw = json.dumps(
            {
                "run_id": run.run_id,
                "policy_digest": run.policy_digest,
                "configuration_digest": run.configuration_digest,
                "namespace_scope": run.namespace_scope,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("ascii")
        return f"extension-workload-checkpoint-integrity:sha256:{hashlib.sha256(raw).hexdigest()}"

    @staticmethod
    def projection_from_records(
        *,
        start: ExtensionWorkloadControlPlaneStart,
        capability_steps: Sequence[StepRecord],
        capability_effects: Sequence[EffectJournalEntryRecord],
        closeout: ExtensionWorkloadControlPlaneCloseout,
    ) -> dict[str, object]:
        return {
            "projection_only": True,
            "projection_source": "control_plane_records",
            "execution_state_authority": "control_plane_records",
            "lane_output_execution_state_authoritative": False,
            "control_plane_run_id": start.run.run_id,
            "control_plane_attempt_id": closeout.attempt.attempt_id,
            "control_plane_attempt_state": closeout.attempt.attempt_state.value,
            "control_plane_namespace_scope": closeout.run.namespace_scope or "",
            "control_plane_start_step_id": start.start_step.step_id,
            "control_plane_start_step_kind": start.start_step.step_kind,
            "control_plane_checkpoint_id": start.checkpoint.checkpoint_id,
            "control_plane_checkpoint_acceptance_id": start.checkpoint_acceptance.acceptance_id,
            "control_plane_capability_step_ids": [step.step_id for step in capability_steps],
            "control_plane_effect_journal_entry_ids": [
                start.start_effect.journal_entry_id,
                *[effect.journal_entry_id for effect in capability_effects],
                closeout.closeout_effect.journal_entry_id,
            ],
            "control_plane_closeout_step_id": closeout.closeout_step.step_id,
            "control_plane_closeout_step_kind": closeout.closeout_step.step_kind,
            "control_plane_final_truth_record_id": closeout.final_truth.final_truth_record_id,
            "control_plane_final_result_class": closeout.final_truth.result_class.value,
        }

    @staticmethod
    def _run_resources(*, extension_id: str) -> list[str]:
        namespace_scope = ExtensionWorkloadControlPlaneService.namespace_scope_for(extension_id=extension_id)
        return [f"namespace:{namespace_scope}", f"extension:{sanitize_name(extension_id)}"]

    @staticmethod
    def _capability_class_for(*, capability_id: str) -> CapabilityClass:
        if capability_id == "speech.transcribe":
            return CapabilityClass.OBSERVE
        if capability_id == "memory.write":
            return CapabilityClass.BOUNDED_LOCAL_MUTATION
        if capability_id == "memory.query":
            return CapabilityClass.OBSERVE
        if capability_id == "voice.turn_control":
            return CapabilityClass.BOUNDED_LOCAL_MUTATION
        if capability_id in {"audio.play", "speech.play_clip"}:
            return CapabilityClass.EXTERNAL_MUTATION
        return CapabilityClass.DETERMINISTIC_COMPUTE

    @staticmethod
    def _capability_target_ref(*, extension_id: str, capability_id: str) -> str:
        if capability_id.startswith("memory."):
            return f"extension-memory:{sanitize_name(extension_id)}"
        if capability_id == "model.generate":
            return f"extension-llm:{sanitize_name(extension_id)}"
        if capability_id == "speech.transcribe":
            return f"extension-voice-input:{sanitize_name(extension_id)}"
        if capability_id == "tts.speak":
            return f"extension-voice-synthesis:{sanitize_name(extension_id)}"
        if capability_id in {"audio.play", "speech.play_clip"}:
            return f"extension-audio-output:{sanitize_name(extension_id)}"
        if capability_id == "voice.turn_control":
            return f"extension-turn-control:{sanitize_name(extension_id)}"
        return f"extension-capability:{sanitize_name(extension_id)}:{sanitize_name(capability_id)}"

    @staticmethod
    def _capability_resources(*, extension_id: str, capability_id: str) -> list[str]:
        return [
            f"namespace:{ExtensionWorkloadControlPlaneService.namespace_scope_for(extension_id=extension_id)}",
            ExtensionWorkloadControlPlaneService._capability_target_ref(
                extension_id=extension_id,
                capability_id=capability_id,
            ),
        ]

    @staticmethod
    def _capability_observed_result(*, call_record: Mapping[str, object]) -> str:
        observed_result = str(call_record.get("observed_result") or "").strip() or "unknown"
        denial_class = str(call_record.get("denial_class") or "").strip()
        error_code = str(call_record.get("error_code") or "").strip()
        suffix = denial_class or error_code
        return f"sdk_capability_{observed_result}" if not suffix else f"sdk_capability_{observed_result}:{suffix}"

    @staticmethod
    def _capability_closure_classification(*, observed_result: str) -> str:
        if observed_result == "success":
            return "step_completed"
        if observed_result == "failure":
            return "step_failed"
        return "step_blocked"

    @staticmethod
    def _closeout_observed_result(outcome: ResultClass) -> str:
        return {
            ResultClass.SUCCESS: "extension_workload_completed",
            ResultClass.BLOCKED: "extension_workload_blocked",
            ResultClass.FAILED: "extension_workload_failed",
        }[outcome]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(UTC).isoformat()

    async def _append_effect(
        self,
        *,
        run: RunRecord,
        attempt: AttemptRecord,
        step: StepRecord,
        effect_id: str,
        journal_entry_id: str,
        intended_target_ref: str,
    ) -> EffectJournalEntryRecord:
        return await self.publication.append_effect_journal_entry(
            journal_entry_id=journal_entry_id,
            effect_id=effect_id,
            run_id=run.run_id,
            attempt_id=attempt.attempt_id,
            step_id=step.step_id,
            authorization_basis_ref=run.admission_decision_receipt_ref,
            publication_timestamp=self._utc_now(),
            intended_target_ref=intended_target_ref,
            observed_result_ref=step.output_ref,
            uncertainty_classification=ResidualUncertaintyClassification.NONE,
            integrity_verification_ref=step.output_ref or run.admission_decision_receipt_ref,
        )

    async def _require_run(self, *, run_id: str) -> RunRecord:
        run = await self.execution_repository.get_run_record(run_id=run_id)
        if run is None:
            raise ExtensionWorkloadControlPlaneError(f"extension workload run not found: {run_id}")
        return run

    async def _require_attempt(self, *, attempt_id: str | None) -> AttemptRecord:
        if not attempt_id:
            raise ExtensionWorkloadControlPlaneError("extension workload attempt id missing")
        attempt = await self.execution_repository.get_attempt_record(attempt_id=attempt_id)
        if attempt is None:
            raise ExtensionWorkloadControlPlaneError(f"extension workload attempt not found: {attempt_id}")
        return attempt

    async def _require_step(self, *, step_id: str) -> StepRecord:
        step = await self.execution_repository.get_step_record(step_id=step_id)
        if step is None:
            raise ExtensionWorkloadControlPlaneError(f"extension workload step not found: {step_id}")
        return step

    async def _require_effect(self, *, run_id: str, stage: str) -> EffectJournalEntryRecord:
        entries = await self.publication.repository.list_effect_journal_entries(run_id=run_id)
        effect_id = self.effect_id_for(run_id=run_id, stage=stage)
        for entry in entries:
            if entry.effect_id == effect_id:
                return entry
        raise ExtensionWorkloadControlPlaneError(f"extension workload effect not found: {effect_id}")


__all__ = [
    "ExtensionWorkloadControlPlaneCloseout",
    "ExtensionWorkloadControlPlaneError",
    "ExtensionWorkloadControlPlaneService",
    "ExtensionWorkloadControlPlaneStart",
]
