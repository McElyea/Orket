"""Application-owned admission and immutable inputs for the outward executor."""

from __future__ import annotations

from typing import Any

from orket.adapters.storage.outward_store_transaction import OutwardStoreTransaction
from orket.application.services.control_plane_publication_service import ControlPlanePublicationService
from orket.application.services.control_plane_snapshot_publication import publish_run_snapshots, snapshot_digest
from orket.application.services.control_plane_workload_catalog import control_plane_workload_for_key
from orket.application.services.outward_run_execution_plan import EXECUTION_STATE_KEY, MODEL_TOOL_CALL_KEY
from orket.application.services.outward_run_lifecycle import terminal_projection
from orket.core.contracts import AttemptRecord, RunRecord
from orket.core.domain import AttemptState, RunState
from orket.core.domain.control_plane_final_truth import (
    ControlPlaneFinalTruthError,
    validate_terminal_record_consistency,
)
from orket.core.domain.control_plane_lifecycle import validate_attempt_state_transition, validate_run_state_transition
from orket.core.domain.outward_authorization import outward_attempt_id
from orket.core.domain.outward_run_events import LedgerEvent
from orket.core.domain.outward_runs import OutwardRunRecord

OUTWARD_AUTHORITY_ADOPTION_EVENT = "outward_authority_adopted"


def authority_adoption_event_id(run_id: str) -> str:
    return f"run:{run_id}:authority-adopted:v1"


def admission_configuration(run: OutwardRunRecord) -> dict[str, Any]:
    workload = control_plane_workload_for_key("outward-governed-tools")
    return {
        "authority_version": 1,
        "workload": workload.model_dump(mode="json"),
        "run_id": run.run_id,
        "execution_generation": run.execution_generation,
        "namespace": run.namespace,
        "submitted_at": run.submitted_at,
        "max_turns": run.max_turns,
        "task": {key: value for key, value in run.task.items() if key not in {EXECUTION_STATE_KEY, MODEL_TOOL_CALL_KEY}},
    }


async def admit_outward_run(
    transaction: OutwardStoreTransaction, run: OutwardRunRecord, *, adoption: LedgerEvent | None = None,
) -> RunRecord:
    cp = transaction.control_plane
    if await cp.execution.get_run_record(run_id=run.run_id) is not None:
        raise RuntimeError("E_OUTWARD_AUTHORITY_ALREADY_EXISTS")
    configuration = admission_configuration(run)
    workload = configuration["workload"]
    attempt_id = outward_attempt_id(run.run_id, run.execution_generation)
    receipt_ref = adoption.event_id if adoption else f"run:{run.run_id}:submitted"
    record = RunRecord(
        run_id=run.run_id, workload_id=workload["workload_id"], workload_version=workload["workload_version"],
        policy_snapshot_id=f"outward-policy:{attempt_id}", policy_digest=snapshot_digest(run.policy_overrides),
        configuration_snapshot_id=f"outward-input:{attempt_id}", configuration_digest=snapshot_digest(configuration),
        creation_timestamp=adoption.at if adoption else run.submitted_at, admission_decision_receipt_ref=receipt_ref,
        namespace_scope=run.namespace, lifecycle_state=RunState.ADMISSION_PENDING, current_attempt_id=attempt_id,
    )
    await publish_run_snapshots(publication=ControlPlanePublicationService(repository=cp.records), run=record,
        policy_payload=run.policy_overrides, policy_source_refs=[receipt_ref],
        configuration_payload=configuration, configuration_source_refs=[receipt_ref])
    validate_run_state_transition(current_state=record.lifecycle_state, next_state=RunState.ADMITTED)
    record = record.model_copy(update={"lifecycle_state": RunState.ADMITTED})
    record = await cp.execution.save_run_record(record=record)
    await cp.execution.save_attempt_record(record=AttemptRecord(
        attempt_id=attempt_id, run_id=run.run_id, attempt_ordinal=run.execution_generation,
        attempt_state=AttemptState.CREATED, starting_state_snapshot_ref=record.configuration_snapshot_id,
        start_timestamp=run.submitted_at,
    ))
    return record


async def require_outward_authority(
    transaction: OutwardStoreTransaction, run: OutwardRunRecord,
) -> tuple[RunRecord, AttemptRecord]:
    run.require_execution_admission()
    cp = transaction.control_plane
    record = await cp.execution.get_run_record(run_id=run.run_id)
    if record is None:
        raise RuntimeError("E_OUTWARD_AUTHORITY_MIGRATION_REQUIRED")
    configuration = await cp.records.get_resolved_configuration_snapshot(snapshot_id=record.configuration_snapshot_id)
    policy = await cp.records.get_resolved_policy_snapshot(snapshot_id=record.policy_snapshot_id)
    if configuration is None or policy is None:
        raise RuntimeError("E_OUTWARD_AUTHORITY_SNAPSHOT_MISSING")
    current = admission_configuration(run)
    if (configuration.configuration_payload != current
            or configuration.snapshot_digest != record.configuration_digest
            or snapshot_digest(configuration.configuration_payload) != record.configuration_digest
            or policy.policy_payload != run.policy_overrides
            or policy.snapshot_digest != record.policy_digest
            or snapshot_digest(policy.policy_payload) != record.policy_digest
            or record.namespace_scope != run.namespace
            or record.workload_id != current["workload"]["workload_id"]
            or record.workload_version != current["workload"]["workload_version"]):
        raise RuntimeError("E_OUTWARD_AUTHORITY_INPUT_DRIFT")
    attempt_id = outward_attempt_id(run.run_id, run.execution_generation)
    attempt = await cp.execution.get_attempt_record(attempt_id=attempt_id)
    if (record.current_attempt_id != attempt_id or attempt is None or attempt.run_id != run.run_id
            or attempt.starting_state_snapshot_ref != record.configuration_snapshot_id
            or attempt.attempt_ordinal != run.execution_generation or attempt.start_timestamp != run.submitted_at):
        raise RuntimeError("E_OUTWARD_AUTHORITY_ATTEMPT_DRIFT")
    await _require_admission_receipt(transaction, run, record)
    return record, attempt


async def _require_admission_receipt(transaction, run, record) -> None:
    receipt = await transaction.get_event(record.admission_decision_receipt_ref)
    if receipt is None or receipt.run_id != run.run_id or receipt.at != record.creation_timestamp:
        raise RuntimeError("E_OUTWARD_AUTHORITY_ADMISSION_RECEIPT_CONFLICT")
    if record.admission_decision_receipt_ref == authority_adoption_event_id(run.run_id):
        if (receipt.event_type != OUTWARD_AUTHORITY_ADOPTION_EVENT
                or receipt.payload.get("configuration_digest") != record.configuration_digest
                or receipt.payload.get("policy_digest") != record.policy_digest):
            raise RuntimeError("E_OUTWARD_AUTHORITY_ADOPTION_RECEIPT_CONFLICT")
    elif (receipt.event_id != f"run:{run.run_id}:submitted" or receipt.event_type != "run_submitted"
            or receipt.at != run.submitted_at or receipt.payload.get("namespace") != run.namespace
            or receipt.payload.get("policy_overrides") != run.policy_overrides):
        raise RuntimeError("E_OUTWARD_AUTHORITY_ADMISSION_RECEIPT_CONFLICT")


async def begin_outward_execution(transaction: OutwardStoreTransaction, run: OutwardRunRecord) -> None:
    record, attempt = await require_outward_authority(transaction, run)
    if record.lifecycle_state is RunState.EXECUTING and attempt.attempt_state is AttemptState.EXECUTING:
        return
    validate_run_state_transition(current_state=record.lifecycle_state, next_state=RunState.EXECUTING)
    validate_attempt_state_transition(current_state=attempt.attempt_state, next_state=AttemptState.EXECUTING)
    record = await transaction.control_plane.execution.save_run_record(record=record.model_copy(update={"lifecycle_state": RunState.EXECUTING}))
    attempt = await transaction.control_plane.execution.save_attempt_record(record=attempt.model_copy(update={"attempt_state": AttemptState.EXECUTING}))


async def outward_status_payload(transaction: OutwardStoreTransaction, run: OutwardRunRecord) -> dict[str, Any]:
    payload = run.to_status_payload()
    record = await transaction.control_plane.execution.get_run_record(run_id=run.run_id)
    if record is None:
        return {**payload, "authority_state": "legacy_quarantined" if run.execution_generation < 1 else "migration_required",
                "final_truth": None}
    record, attempt = await require_outward_authority(transaction, run)
    try:
        truth = await transaction.control_plane.records.get_final_truth(run_id=run.run_id)
        validate_terminal_record_consistency(record, attempt, truth)
    except ControlPlaneFinalTruthError as exc:
        raise RuntimeError("E_OUTWARD_FINAL_TRUTH_PROJECTION_CONFLICT") from exc
    terminal = run.status in {"completed", "failed"}
    if terminal != (truth is not None):
        raise RuntimeError("E_OUTWARD_FINAL_TRUTH_PROJECTION_CONFLICT")
    if truth is not None:
        step = await transaction.control_plane.execution.get_step_record(step_id=truth.authoritative_result_ref)
        event = await transaction.get_event(step.output_ref) if step else None
        if (step is None or event is None or step.attempt_id != record.current_attempt_id
                or record.lifecycle_state not in {RunState.COMPLETED, RunState.FAILED_TERMINAL}
                or attempt.attempt_state not in {AttemptState.COMPLETED, AttemptState.FAILED}
                or attempt.end_timestamp != run.completed_at or run.completed_at is None
                or step.step_kind != "outward_terminal" or step.namespace_scope != run.namespace
                or step.input_ref != record.configuration_snapshot_id or not step.receipt_refs
                or step.observed_result_classification != truth.result_class.value or event.run_id != run.run_id
                or terminal_projection(step.closure_classification) != (run.status, truth.result_class)
                or event.payload.get("final_truth_record_id") != truth.final_truth_record_id
                or event.payload.get("final_truth_digest") != snapshot_digest(truth.model_dump(mode="json"))):
            raise RuntimeError("E_OUTWARD_FINAL_TRUTH_PROJECTION_CONFLICT")
    elif (attempt.end_timestamp is not None
            or record.lifecycle_state not in {RunState.ADMITTED, RunState.EXECUTING}
            or attempt.attempt_state not in {AttemptState.CREATED, AttemptState.EXECUTING}):
        raise RuntimeError("E_OUTWARD_FINAL_TRUTH_PROJECTION_CONFLICT")
    return {**payload, "authority_state": "shared", "workload_id": record.workload_id,
            "workload_version": record.workload_version, "final_truth": truth.model_dump(mode="json") if truth else None}
