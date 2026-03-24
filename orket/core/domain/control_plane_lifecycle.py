from __future__ import annotations

from dataclasses import dataclass

from orket.core.domain.control_plane_enums import AttemptState, RunState


class ControlPlaneLifecycleError(ValueError):
    """Raised when an invalid control-plane lifecycle transition is attempted."""


TERMINAL_RUN_STATES = frozenset(
    {
        RunState.COMPLETED,
        RunState.FAILED_TERMINAL,
        RunState.CANCELLED,
    }
)

TERMINAL_ATTEMPT_STATES = frozenset(
    {
        AttemptState.FAILED,
        AttemptState.INTERRUPTED,
        AttemptState.COMPLETED,
        AttemptState.ABANDONED,
    }
)

_RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.CREATED: frozenset({RunState.ADMISSION_PENDING, RunState.CANCELLED}),
    RunState.ADMISSION_PENDING: frozenset({RunState.ADMITTED, RunState.FAILED_TERMINAL, RunState.CANCELLED}),
    RunState.ADMITTED: frozenset({RunState.EXECUTING, RunState.CANCELLED}),
    RunState.EXECUTING: frozenset(
        {
            RunState.WAITING_ON_OBSERVATION,
            RunState.WAITING_ON_RESOURCE,
            RunState.RECONCILING,
            RunState.RECOVERY_PENDING,
            RunState.OPERATOR_BLOCKED,
            RunState.QUARANTINED,
            RunState.COMPLETED,
            RunState.FAILED_TERMINAL,
            RunState.CANCELLED,
        }
    ),
    RunState.WAITING_ON_OBSERVATION: frozenset({RunState.EXECUTING, RunState.RECOVERY_PENDING, RunState.CANCELLED}),
    RunState.WAITING_ON_RESOURCE: frozenset({RunState.EXECUTING, RunState.RECOVERY_PENDING, RunState.CANCELLED}),
    RunState.RECOVERY_PENDING: frozenset(
        {
            RunState.RECONCILING,
            RunState.RECOVERING,
            RunState.OPERATOR_BLOCKED,
            RunState.QUARANTINED,
            RunState.CANCELLED,
        }
    ),
    RunState.RECONCILING: frozenset(
        {
            RunState.RECOVERING,
            RunState.OPERATOR_BLOCKED,
            RunState.COMPLETED,
            RunState.FAILED_TERMINAL,
            RunState.CANCELLED,
        }
    ),
    RunState.RECOVERING: frozenset(
        {
            RunState.EXECUTING,
            RunState.COMPLETED,
            RunState.RECOVERY_PENDING,
            RunState.QUARANTINED,
            RunState.CANCELLED,
        }
    ),
    RunState.OPERATOR_BLOCKED: frozenset({RunState.RECOVERING, RunState.FAILED_TERMINAL, RunState.CANCELLED}),
    RunState.QUARANTINED: frozenset({RunState.RECOVERING, RunState.FAILED_TERMINAL, RunState.CANCELLED}),
    RunState.COMPLETED: frozenset(),
    RunState.FAILED_TERMINAL: frozenset(),
    RunState.CANCELLED: frozenset(),
}

_ATTEMPT_TRANSITIONS: dict[AttemptState, frozenset[AttemptState]] = {
    AttemptState.CREATED: frozenset({AttemptState.EXECUTING, AttemptState.ABANDONED}),
    AttemptState.EXECUTING: frozenset(
        {
            AttemptState.WAITING,
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
            AttemptState.COMPLETED,
            AttemptState.ABANDONED,
        }
    ),
    AttemptState.WAITING: frozenset(
        {
            AttemptState.EXECUTING,
            AttemptState.FAILED,
            AttemptState.INTERRUPTED,
            AttemptState.ABANDONED,
        }
    ),
    AttemptState.FAILED: frozenset(),
    AttemptState.INTERRUPTED: frozenset(),
    AttemptState.COMPLETED: frozenset(),
    AttemptState.ABANDONED: frozenset(),
}


@dataclass(frozen=True)
class RunTransitionRequirement:
    current_state: RunState
    next_state: RunState
    guard_summary: str
    required_evidence: tuple[str, ...]
    allowed_actor: str
    forbidden_shortcuts: tuple[str, ...]
    truth_constraints: tuple[str, ...]


_RUN_TRANSITION_REQUIREMENTS: dict[tuple[RunState, RunState], RunTransitionRequirement] = {
    (RunState.ADMITTED, RunState.EXECUTING): RunTransitionRequirement(
        current_state=RunState.ADMITTED,
        next_state=RunState.EXECUTING,
        guard_summary="admission accepted; required reservations or prerequisites exist",
        required_evidence=("admission_decision_receipt", "reservation_references_if_applicable"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("start_without_admission_receipt",),
        truth_constraints=("run_remains_attributable_to_admission_and_initial_execution_mode",),
    ),
    (RunState.EXECUTING, RunState.RECOVERY_PENDING): RunTransitionRequirement(
        current_state=RunState.EXECUTING,
        next_state=RunState.RECOVERY_PENDING,
        guard_summary="attempt ended without truthful closure",
        required_evidence=("failed_or_interrupted_attempt_record", "side_effect_boundary_classification"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("immediate_blind_retry",),
        truth_constraints=("run_must_not_return_to_executing_without_recovery_decision",),
    ),
    (RunState.RECOVERY_PENDING, RunState.RECONCILING): RunTransitionRequirement(
        current_state=RunState.RECOVERY_PENDING,
        next_state=RunState.RECONCILING,
        guard_summary="policy or uncertainty requires observation before recovery",
        required_evidence=("reconciliation_trigger_basis", "required_scope"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("treat_unresolved_uncertainty_as_pre_effect_convenience",),
        truth_constraints=("continuation_waits_for_reconciliation_output",),
    ),
    (RunState.RECONCILING, RunState.RECOVERING): RunTransitionRequirement(
        current_state=RunState.RECONCILING,
        next_state=RunState.RECOVERING,
        guard_summary="reconciliation published a continuation class requiring control-plane recovery work",
        required_evidence=("reconciliation_record", "authorized_recovery_decision"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("treat_reconciliation_as_execution_restart",),
        truth_constraints=("recovering_remains_control_plane_work_only",),
    ),
    (RunState.RECOVERING, RunState.EXECUTING): RunTransitionRequirement(
        current_state=RunState.RECOVERING,
        next_state=RunState.EXECUTING,
        guard_summary="authorized recovery work completed and workload execution may continue",
        required_evidence=("recovery_action_receipt", "attempt_bootstrap_or_resume_basis"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("continue_without_recovery_completion_receipt",),
        truth_constraints=("resumed_or_replacement_execution_reenters_executing",),
    ),
    (RunState.EXECUTING, RunState.OPERATOR_BLOCKED): RunTransitionRequirement(
        current_state=RunState.EXECUTING,
        next_state=RunState.OPERATOR_BLOCKED,
        guard_summary="bounded human decision required and quarantine not yet warranted",
        required_evidence=("operator_requirement_basis", "unresolved_decision_surface"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("hidden_human_assumption", "hidden_pause"),
        truth_constraints=("run_remains_explicitly_blocked_pending_operator_input",),
    ),
    (RunState.EXECUTING, RunState.QUARANTINED): RunTransitionRequirement(
        current_state=RunState.EXECUTING,
        next_state=RunState.QUARANTINED,
        guard_summary="contradiction, unsafe ownership, or policy breach requires isolation",
        required_evidence=("violation_basis", "quarantine_reason"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("continue_in_degraded_mode_by_convenience",),
        truth_constraints=("automatic_continuation_disabled_until_explicit_release",),
    ),
    (RunState.OPERATOR_BLOCKED, RunState.RECOVERING): RunTransitionRequirement(
        current_state=RunState.OPERATOR_BLOCKED,
        next_state=RunState.RECOVERING,
        guard_summary="explicit operator input permits a control-plane recovery action",
        required_evidence=("operator_action_receipt", "recovery_decision"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("treat_operator_input_as_world_state_evidence",),
        truth_constraints=("operator_input_may_change_continuation_but_not_truth_classification",),
    ),
    (RunState.QUARANTINED, RunState.FAILED_TERMINAL): RunTransitionRequirement(
        current_state=RunState.QUARANTINED,
        next_state=RunState.FAILED_TERMINAL,
        guard_summary="safe continuation remains unavailable",
        required_evidence=("terminal_decision_basis", "required_policy_or_operator_confirmation"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("auto_release_quarantine_into_terminal_closure_without_basis",),
        truth_constraints=("final_closure_explains_why_continuation_stopped",),
    ),
    (RunState.OPERATOR_BLOCKED, RunState.FAILED_TERMINAL): RunTransitionRequirement(
        current_state=RunState.OPERATOR_BLOCKED,
        next_state=RunState.FAILED_TERMINAL,
        guard_summary="operator or policy chooses terminal stop instead of continuation",
        required_evidence=("operator_action_or_policy_basis", "closure_basis"),
        allowed_actor="supervisor",
        forbidden_shortcuts=("mark_terminal_as_successful_completion",),
        truth_constraints=("terminality_may_change_but_truth_classification_may_not_be_rewritten_by_command",),
    ),
}


def allowed_run_transitions(current_state: RunState) -> frozenset[RunState]:
    return _RUN_TRANSITIONS[current_state]


def is_terminal_run_state(state: RunState) -> bool:
    return state in TERMINAL_RUN_STATES


def allowed_attempt_transitions(current_state: AttemptState) -> frozenset[AttemptState]:
    return _ATTEMPT_TRANSITIONS[current_state]


def is_terminal_attempt_state(state: AttemptState) -> bool:
    return state in TERMINAL_ATTEMPT_STATES


def validate_run_state_transition(*, current_state: RunState, next_state: RunState) -> bool:
    allowed = _RUN_TRANSITIONS[current_state]
    if next_state not in allowed:
        raise ControlPlaneLifecycleError(
            f"Illegal control-plane run transition: {current_state.value} -> {next_state.value}."
        )
    return True


def validate_attempt_state_transition(*, current_state: AttemptState, next_state: AttemptState) -> bool:
    allowed = _ATTEMPT_TRANSITIONS[current_state]
    if next_state not in allowed:
        raise ControlPlaneLifecycleError(
            f"Illegal control-plane attempt transition: {current_state.value} -> {next_state.value}."
        )
    return True


def get_run_transition_requirement(
    *, current_state: RunState, next_state: RunState
) -> RunTransitionRequirement | None:
    return _RUN_TRANSITION_REQUIREMENTS.get((current_state, next_state))


__all__ = [
    "ControlPlaneLifecycleError",
    "RunTransitionRequirement",
    "TERMINAL_ATTEMPT_STATES",
    "TERMINAL_RUN_STATES",
    "allowed_attempt_transitions",
    "allowed_run_transitions",
    "get_run_transition_requirement",
    "is_terminal_attempt_state",
    "is_terminal_run_state",
    "validate_attempt_state_transition",
    "validate_run_state_transition",
]
