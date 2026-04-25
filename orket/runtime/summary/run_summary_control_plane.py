from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from orket.core.contracts import AttemptRecord, CheckpointAcceptanceRecord, CheckpointRecord, RunRecord, StepRecord

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def build_control_plane_summary_projection(*, artifacts: dict[str, Any]) -> dict[str, Any] | None:
    run_record = _validated_record(artifacts.get("control_plane_run_record"), RunRecord)
    attempt_record = _validated_record(artifacts.get("control_plane_attempt_record"), AttemptRecord)
    step_record = _validated_record(artifacts.get("control_plane_step_record"), StepRecord)
    checkpoint_record = _validated_record(artifacts.get("control_plane_checkpoint_record"), CheckpointRecord)
    checkpoint_acceptance_record = _validated_record(
        artifacts.get("control_plane_checkpoint_acceptance_record"),
        CheckpointAcceptanceRecord,
    )
    if (
        run_record is None
        and attempt_record is None
        and step_record is None
        and checkpoint_record is None
        and checkpoint_acceptance_record is None
    ):
        return None

    payload: dict[str, Any] = {
        "projection_source": "control_plane_records",
        "projection_only": True,
    }
    if run_record is not None:
        payload.update(
            {
                "run_id": run_record["run_id"],
                "run_state": run_record["lifecycle_state"],
                "workload_id": run_record["workload_id"],
                "workload_version": run_record["workload_version"],
                "policy_snapshot_id": run_record["policy_snapshot_id"],
                "configuration_snapshot_id": run_record["configuration_snapshot_id"],
                "current_attempt_id": run_record.get("current_attempt_id"),
            }
        )
        namespace_scope = str(run_record.get("namespace_scope") or "").strip()
        if namespace_scope:
            payload["namespace_scope"] = namespace_scope
    if attempt_record is not None:
        payload.update(
            {
                "attempt_id": attempt_record["attempt_id"],
                "attempt_state": attempt_record["attempt_state"],
                "attempt_ordinal": int(attempt_record["attempt_ordinal"]),
            }
        )
        failure_class = str(attempt_record.get("failure_class") or "").strip()
        if failure_class:
            payload["failure_class"] = failure_class
        failure_plane = str(attempt_record.get("failure_plane") or "").strip()
        if failure_plane:
            payload["failure_plane"] = failure_plane
        failure_classification = str(attempt_record.get("failure_classification") or "").strip()
        if failure_classification:
            payload["failure_classification"] = failure_classification
        recovery_decision_id = str(attempt_record.get("recovery_decision_id") or "").strip()
        if recovery_decision_id:
            payload["recovery_decision_id"] = recovery_decision_id
    if step_record is not None:
        payload.update(
            {
                "step_id": step_record["step_id"],
                "step_kind": step_record["step_kind"],
            }
        )
        step_namespace_scope = str(step_record.get("namespace_scope") or "").strip()
        if step_namespace_scope:
            payload["step_namespace_scope"] = step_namespace_scope
        capability_used = str(step_record.get("capability_used") or "").strip()
        if capability_used:
            payload["step_capability_used"] = capability_used
        resources_touched = [
            str(token).strip() for token in (step_record.get("resources_touched") or []) if str(token).strip()
        ]
        if resources_touched:
            payload["step_resources_touched"] = resources_touched
        receipt_refs = [str(token).strip() for token in (step_record.get("receipt_refs") or []) if str(token).strip()]
        if receipt_refs:
            payload["step_receipt_refs"] = receipt_refs
    if checkpoint_record is not None:
        payload["checkpoint_id"] = checkpoint_record["checkpoint_id"]
        payload["checkpoint_resumability_class"] = checkpoint_record["resumability_class"]
    if checkpoint_acceptance_record is not None:
        payload["checkpoint_acceptance_id"] = checkpoint_acceptance_record["acceptance_id"]
        payload["checkpoint_acceptance_outcome"] = checkpoint_acceptance_record["outcome"]
    return payload


def _validated_record(value: Any, model_type: type[_ModelT]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return model_type.model_validate(value).model_dump(mode="json")


__all__ = ["build_control_plane_summary_projection"]
