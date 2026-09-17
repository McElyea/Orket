"""Explicit observed revisions for mutable execution records; no hidden caller state."""
from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from orket.core.domain.control_plane_enums import AttemptState

if TYPE_CHECKING:
    from orket.core.contracts.control_plane_models import AttemptRecord, RunRecord, StepRecord

ExecutionRecord = TypeVar('ExecutionRecord', bound='RunRecord | AttemptRecord | StepRecord')
ATTEMPT_STATE_FIELDS = frozenset({'state_revision', 'attempt_state', 'end_timestamp', 'side_effect_boundary_class',
                                'failure_plane', 'failure_classification', 'failure_class', 'recovery_decision_id'})
STEP_STATE_FIELDS = frozenset({'state_revision', 'output_ref', 'capability_used', 'resources_touched',
                             'observed_result_classification', 'receipt_refs', 'closure_classification'})


def read_execution_record(record_type: type[ExecutionRecord], payload: str) -> ExecutionRecord:
    record = record_type.model_validate_json(payload)
    if record.state_revision is None:
        if 'state_revision' in record.model_fields_set:
            raise ValueError('E_CONTROL_PLANE_STATE_CONFLICT: persisted revision cannot be null')
        # Historical rows expose baseline revision zero without rewriting retained bytes.
        record = record.model_copy(update={'state_revision': 0})
    return record


def next_execution_record(existing: ExecutionRecord | None, incoming: ExecutionRecord,
                          error_type: type[Exception]) -> ExecutionRecord:
    if existing is None:
        if incoming.state_revision is not None:
            raise error_type('E_CONTROL_PLANE_STATE_CONFLICT: observed identity no longer exists')
        return incoming.model_copy(update={'state_revision': 0})
    if incoming.state_revision is None or incoming.state_revision != existing.state_revision:
        raise error_type('E_CONTROL_PLANE_STATE_CONFLICT: creation requires absence; update requires current revision')
    if incoming == existing:
        return existing
    return incoming.model_copy(update={'state_revision': existing.state_revision + 1})


def same_attempt_admission(existing: AttemptRecord, incoming: AttemptRecord) -> bool:
    mutable = ATTEMPT_STATE_FIELDS
    if existing.attempt_state is AttemptState.CREATED and incoming.attempt_state is AttemptState.EXECUTING:
        mutable = mutable | {'start_timestamp'}
    return existing.model_dump(exclude=mutable) == incoming.model_dump(exclude=mutable)


def same_step_admission(existing: StepRecord, incoming: StepRecord) -> bool:
    return existing.model_dump(exclude=STEP_STATE_FIELDS) == incoming.model_dump(exclude=STEP_STATE_FIELDS)
