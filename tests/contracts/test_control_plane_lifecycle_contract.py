# Layer: contract

from __future__ import annotations

import pytest

from orket.core.domain import (
    AttemptState,
    ControlPlaneLifecycleError,
    RunState,
    TERMINAL_ATTEMPT_STATES,
    TERMINAL_RUN_STATES,
    allowed_attempt_transitions,
    allowed_run_transitions,
    get_run_transition_requirement,
    is_terminal_attempt_state,
    is_terminal_run_state,
    validate_attempt_state_transition,
    validate_run_state_transition,
)


pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (RunState.CREATED, RunState.ADMISSION_PENDING),
        (RunState.ADMITTED, RunState.EXECUTING),
        (RunState.EXECUTING, RunState.RECOVERY_PENDING),
        (RunState.EXECUTING, RunState.OPERATOR_BLOCKED),
        (RunState.EXECUTING, RunState.QUARANTINED),
        (RunState.RECOVERY_PENDING, RunState.RECONCILING),
        (RunState.RECONCILING, RunState.RECOVERING),
        (RunState.RECOVERING, RunState.EXECUTING),
        (RunState.OPERATOR_BLOCKED, RunState.RECOVERING),
        (RunState.QUARANTINED, RunState.FAILED_TERMINAL),
    ],
)
def test_run_transition_matrix_accepts_required_paths(current_state: RunState, next_state: RunState) -> None:
    assert validate_run_state_transition(current_state=current_state, next_state=next_state) is True


@pytest.mark.parametrize(
    "current_state",
    [
        RunState.CREATED,
        RunState.ADMISSION_PENDING,
        RunState.ADMITTED,
        RunState.EXECUTING,
        RunState.WAITING_ON_OBSERVATION,
        RunState.WAITING_ON_RESOURCE,
        RunState.RECOVERY_PENDING,
        RunState.RECONCILING,
        RunState.RECOVERING,
        RunState.OPERATOR_BLOCKED,
        RunState.QUARANTINED,
    ],
)
def test_any_non_terminal_run_state_can_cancel(current_state: RunState) -> None:
    assert validate_run_state_transition(current_state=current_state, next_state=RunState.CANCELLED) is True


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (RunState.RECOVERING, RunState.OPERATOR_BLOCKED),
        (RunState.QUARANTINED, RunState.EXECUTING),
        (RunState.COMPLETED, RunState.CANCELLED),
        (RunState.FAILED_TERMINAL, RunState.RECOVERING),
        (RunState.CANCELLED, RunState.EXECUTING),
    ],
)
def test_run_transition_matrix_rejects_forbidden_paths(current_state: RunState, next_state: RunState) -> None:
    with pytest.raises(ControlPlaneLifecycleError):
        validate_run_state_transition(current_state=current_state, next_state=next_state)


def test_terminal_run_states_match_contract() -> None:
    assert TERMINAL_RUN_STATES == frozenset(
        {
            RunState.COMPLETED,
            RunState.FAILED_TERMINAL,
            RunState.CANCELLED,
        }
    )
    assert is_terminal_run_state(RunState.COMPLETED) is True
    assert is_terminal_run_state(RunState.EXECUTING) is False


def test_allowed_run_transitions_keep_recovering_distinct_from_ordinary_execution() -> None:
    allowed = allowed_run_transitions(RunState.RECOVERING)

    assert RunState.EXECUTING in allowed
    assert RunState.OPERATOR_BLOCKED not in allowed


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (AttemptState.CREATED, AttemptState.EXECUTING),
        (AttemptState.EXECUTING, AttemptState.WAITING),
        (AttemptState.EXECUTING, AttemptState.FAILED),
        (AttemptState.WAITING, AttemptState.EXECUTING),
        (AttemptState.WAITING, AttemptState.ABANDONED),
    ],
)
def test_attempt_transition_matrix_accepts_required_paths(current_state: AttemptState, next_state: AttemptState) -> None:
    assert validate_attempt_state_transition(current_state=current_state, next_state=next_state) is True


@pytest.mark.parametrize(
    ("current_state", "next_state"),
    [
        (AttemptState.CREATED, AttemptState.COMPLETED),
        (AttemptState.FAILED, AttemptState.EXECUTING),
        (AttemptState.INTERRUPTED, AttemptState.ABANDONED),
        (AttemptState.COMPLETED, AttemptState.WAITING),
    ],
)
def test_attempt_transition_matrix_rejects_forbidden_paths(current_state: AttemptState, next_state: AttemptState) -> None:
    with pytest.raises(ControlPlaneLifecycleError):
        validate_attempt_state_transition(current_state=current_state, next_state=next_state)


def test_terminal_attempt_states_match_contract() -> None:
    assert TERMINAL_ATTEMPT_STATES == frozenset(
        {
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
            AttemptState.COMPLETED,
            AttemptState.ABANDONED,
        }
    )
    assert is_terminal_attempt_state(AttemptState.COMPLETED) is True
    assert is_terminal_attempt_state(AttemptState.WAITING) is False


def test_allowed_attempt_transitions_keep_terminal_attempts_closed() -> None:
    assert allowed_attempt_transitions(AttemptState.FAILED) == frozenset()


def test_guard_catalog_exposes_risky_transition_requirement() -> None:
    requirement = get_run_transition_requirement(
        current_state=RunState.EXECUTING,
        next_state=RunState.RECOVERY_PENDING,
    )

    assert requirement is not None
    assert requirement.allowed_actor == "supervisor"
    assert "immediate_blind_retry" in requirement.forbidden_shortcuts
    assert "side_effect_boundary_classification" in requirement.required_evidence


def test_guard_catalog_preserves_operator_terminal_truth_boundary() -> None:
    requirement = get_run_transition_requirement(
        current_state=RunState.OPERATOR_BLOCKED,
        next_state=RunState.FAILED_TERMINAL,
    )

    assert requirement is not None
    assert "mark_terminal_as_successful_completion" in requirement.forbidden_shortcuts
    assert "truth_classification_may_not_be_rewritten_by_command" in requirement.truth_constraints[0]
