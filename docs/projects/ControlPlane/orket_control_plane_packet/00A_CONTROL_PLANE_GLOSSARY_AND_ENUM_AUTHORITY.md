# Control-Plane Glossary and Enum Authority
Last updated: 2026-03-23
Status: Accepted for implementation planning
Owner: Orket Core
Lane type: Control-plane foundation / canonical authority

## Purpose

Define the single canonical noun and enum authority for the ControlPlane packet.

All subordinate packet documents must consume this glossary.
They may explain meaning, guardrails, and policy, but they must not silently redefine shared control-plane vocabulary.

## Authority rules

1. This document is the canonical authority for:
   1. first-class control-plane object nouns
   2. lifecycle enums
   3. failure-plane and failure-class enums
   4. capability and effect enums
   5. reservation and lease status enums
   6. divergence and continuation enums
   7. operator input and command enums
   8. journal and checkpoint enums
   9. final-truth enums
2. A subordinate document may narrow allowed combinations, add guard conditions, or define semantics.
3. A subordinate document may not introduce a conflicting synonym for an existing enum or object noun.
4. If a new shared enum is required later, it must be added here first.

## Architecture alignment

`FinalTruthRecord.result_class` must use the stable result vocabulary already defined in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

This packet augments that result vocabulary with additional closure fields.
It does not silently replace it.

## Canonical object nouns

The following nouns are first-class control-plane objects:

1. `Workload`
2. `Run`
3. `Attempt`
4. `Step`
5. `Effect`
6. `Resource`
7. `Reservation`
8. `Lease`
9. `Checkpoint`
10. `RecoveryDecision`
11. `ReconciliationRecord`
12. `OperatorAction`
13. `FinalTruthRecord`
14. `EffectJournalEntry`
15. `CheckpointAcceptanceRecord`

## Run lifecycle states

Canonical run states:

1. `created`
2. `admission_pending`
3. `admitted`
4. `executing`
5. `waiting_on_observation`
6. `waiting_on_resource`
7. `recovery_pending`
8. `reconciling`
9. `recovering`
10. `operator_blocked`
11. `quarantined`
12. `completed`
13. `failed_terminal`
14. `cancelled`

Terminal run states:

1. `completed`
2. `failed_terminal`
3. `cancelled`

## Attempt lifecycle states

Canonical attempt states:

1. `attempt_created`
2. `attempt_executing`
3. `attempt_waiting`
4. `attempt_failed`
5. `attempt_interrupted`
6. `attempt_completed`
7. `attempt_abandoned`

## Failure planes

Canonical primary failure planes:

1. `execution_failure`
2. `protocol_failure`
3. `truth_failure`
4. `resource_failure`
5. `control_plane_failure`

## Failure classes

Execution failure classes:

1. `adapter_execution_failure`
2. `tool_timeout`
3. `transport_failure`
4. `deterministic_transform_failure`
5. `checkpoint_invalid`
6. `resume_failure`

Protocol failure classes:

1. `invalid_envelope`
2. `invalid_schema`
3. `tool_cardinality_violation`
4. `forbidden_mixed_surface`
5. `missing_required_observation`
6. `undeclared_capability_request`

Truth failure classes:

1. `unsupported_claim`
2. `missing_required_evidence`
3. `tool_result_contradiction`
4. `state_contradiction`
5. `claim_exceeds_authority`
6. `false_completion_claim`

Resource failure classes:

1. `lease_conflict`
2. `resource_unavailable`
3. `resource_state_uncertain`
4. `orphan_resource_detected`
5. `cleanup_authority_blocked`
6. `reservation_conflict`
7. `reservation_expired_before_execution`

Control-plane failure classes:

1. `illegal_state_transition`
2. `journal_integrity_failure`
3. `missing_required_receipt`
4. `supervisory_invariant_violation`
5. `reconciliation_publication_failure`
6. `final_truth_publication_failure`

## Side-effect boundary classes

Canonical side-effect boundary classes:

1. `pre_effect_failure`
2. `effect_boundary_uncertain`
3. `post_effect_observed`

## Recovery action classes

Canonical recovery action classes:

1. `retry_same_attempt_scope`
2. `start_new_attempt`
3. `resume_from_checkpoint`
4. `require_observation_then_continue`
5. `require_reconciliation_then_decide`
6. `perform_control_plane_recovery_action`
7. `downgrade_to_degraded_mode`
8. `quarantine_run`
9. `escalate_to_operator`
10. `terminate_run`

## Capability classes

Canonical capability classes:

1. `observe`
2. `deterministic_compute`
3. `bounded_local_mutation`
4. `external_mutation`
5. `destructive_mutation`
6. `operator_authorized_action`

## Effect classes

Canonical effect classes:

1. `no_effect`
2. `local_state_effect`
3. `artifact_effect`
4. `resource_lifecycle_effect`
5. `external_service_effect`
6. `destructive_effect`

## Idempotency classes

Canonical idempotency classes:

1. `idempotent`
2. `idempotent_with_token`
3. `non_idempotent`
4. `unknown_idempotency`

## Compensation classes

Canonical compensation classes:

1. `no_compensation_needed`
2. `runtime_compensable`
3. `adapter_compensable`
4. `operator_compensable`
5. `non_compensable`
6. `unknown_compensation`

## Evidence contract classes

Canonical evidence contract classes:

1. `receipt_only`
2. `receipt_plus_observation`
3. `observation_only`
4. `artifact_manifest_required`
5. `external_confirmation_required`
6. `attestation_permitted_by_policy`

## Observability classes

Canonical observability classes:

1. `fully_observable`
2. `eventually_observable`
3. `partially_observable`
4. `opaque_without_external_check`

## Reservation classes

Canonical reservation kind classes:

1. `resource_reservation`
2. `concurrency_reservation`
3. `namespace_reservation`
4. `operator_hold_reservation`

Canonical reservation status classes:

1. `reservation_pending`
2. `reservation_active`
3. `reservation_promoted_to_lease`
4. `reservation_released`
5. `reservation_expired`
6. `reservation_cancelled`
7. `reservation_invalidated`
8. `reservation_uncertain`

## Lease classes

Canonical lease status classes:

1. `lease_pending`
2. `lease_active`
3. `lease_expired`
4. `lease_released`
5. `lease_revoked`
6. `lease_uncertain`

## Cleanup authority classes

Canonical cleanup authority classes:

1. `runtime_cleanup_allowed`
2. `runtime_cleanup_after_reconciliation`
3. `operator_cleanup_required`
4. `adapter_cleanup_only`
5. `cleanup_forbidden_without_external_confirmation`

## Ownership and orphan classes

Canonical ownership classes:

1. `run_owned`
2. `attempt_owned`
3. `shared_governed`
4. `operator_owned`
5. `external_unowned_reference`

Canonical orphan classes:

1. `not_orphaned`
2. `verified_orphan`
3. `suspected_orphan`
4. `ownership_conflict`

## Divergence and continuation classes

Canonical divergence classes:

1. `no_divergence`
2. `expected_effect_observed`
3. `effect_missing`
4. `unexpected_effect_observed`
5. `resource_state_diverged`
6. `ownership_diverged`
7. `insufficient_observation`

Canonical safe continuation classes:

1. `safe_to_continue`
2. `safe_to_continue_in_degraded_mode`
3. `operator_required`
4. `unsafe_to_continue`
5. `terminal_without_cleanup`
6. `cleanup_before_continue`

## Operator input classes

Canonical operator input classes:

1. `operator_command`
2. `operator_risk_acceptance`
3. `operator_attestation`

Canonical operator command classes:

1. `approve_continue`
2. `approve_degraded_continue`
3. `force_reconcile`
4. `quarantine_run`
5. `cancel_run`
6. `release_or_revoke_lease`
7. `approve_cleanup`
8. `mark_terminal`

## Journal and checkpoint enums

Canonical checkpoint acceptance outcome classes:

1. `checkpoint_accepted`
2. `checkpoint_rejected`

Canonical checkpoint re-observation classes:

1. `no_reobservation_required`
2. `target_reobservation_required`
3. `dependency_reobservation_required`
4. `full_reobservation_required`

Canonical checkpoint resumability classes:

1. `resume_same_attempt`
2. `resume_new_attempt_from_checkpoint`
3. `resume_forbidden`

## Final-truth enums

`FinalTruthRecord.result_class` must use:

1. `success`
2. `failed`
3. `blocked`
4. `degraded`
5. `advisory`

Canonical completion classifications:

1. `completion_satisfied`
2. `completion_partial`
3. `completion_unsatisfied`

Canonical evidence sufficiency classifications:

1. `evidence_sufficient`
2. `evidence_attested`
3. `evidence_insufficient`

Canonical residual uncertainty classifications:

1. `no_residual_uncertainty`
2. `bounded_residual_uncertainty`
3. `unresolved_residual_uncertainty`

Canonical degradation classifications:

1. `no_degradation`
2. `declared_degradation`
3. `operator_approved_degradation`

Canonical closure basis classifications:

1. `normal_execution`
2. `reconciliation_closed`
3. `policy_terminal_stop`
4. `operator_terminal_stop`
5. `cancelled_by_authority`

Canonical terminality basis classifications:

1. `completed_terminal`
2. `policy_terminal`
3. `operator_terminal`
4. `cancelled_terminal`

Canonical authority source classes:

1. `receipt_evidence`
2. `adapter_observation`
3. `reconciliation_record`
4. `lease_record`
5. `validated_artifact`
6. `operator_attestation`

## Normative semantic locks

### Reservation is first-class

`Reservation` is a first-class control-plane object.

Reservation means:
1. pre-execution claim on capacity, resource scope, or concurrency scope
2. admission or scheduling truth that can block or permit later execution
3. non-owner state that may later promote into a `Lease`

### Lease is active execution authority

`Lease` means:
1. active ownership or mutation authority over a resource
2. execution-time control strong enough to require fencing
3. state that may survive crashes, retries, reconciliation, or cleanup

Reservation and lease are related but not interchangeable.

### Recovering is control-plane activity

`recovering` means:
1. control-plane recovery work is in progress
2. the runtime is executing an authorized recovery action such as cleanup, lease transfer, checkpoint invalidation, degraded-mode setup, or attempt bootstrap

`recovering` does not mean ordinary workload execution.

Resumed or replacement workload execution returns to:
1. `executing`

### Reconciling is observation and comparison work

`reconciling` means:
1. the runtime is collecting observations
2. intended and observed state are being compared
3. continuation safety is being classified

`reconciling` is distinct from `recovering`.

### FinalTruthRecord is first-class

`FinalTruthRecord` is a first-class control-plane object.

Run closure must reference a `FinalTruthRecord` instead of relying on a loose final-status field.

### Operator truth boundary

1. Operator commands may affect terminality, cleanup authorization, and continuation.
2. Operator commands may not rewrite truth classification.
3. Operator risk acceptance is never evidence of world state.
4. Operator attestation is distinct from adapter observation.
5. Operator attestation is allowed only when policy explicitly permits it for a bounded scope.
6. Operator attestation must remain visibly labeled as attested rather than observed.

## Acceptance intent

This glossary is acceptable only when:
1. every packet document references it for shared vocabulary
2. reservation and final-truth surfaces remain first-class across the packet
3. recovery, reconciliation, and operator docs all consume the same terms
4. future code can import one enum family instead of reconstructing it from prose
