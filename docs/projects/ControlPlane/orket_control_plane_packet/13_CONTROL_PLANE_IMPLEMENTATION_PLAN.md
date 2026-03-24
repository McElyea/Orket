# Control-Plane Implementation Plan
Last updated: 2026-03-24
Status: Active
Owner: Orket Core
Lane type: Priority Now implementation plan
Source contract index: [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)

## Objective

Turn the accepted ControlPlane packet v2 into an implementation-sequenced lane that:
1. lands canonical control-plane contracts first
2. keeps current-state migration honest
3. avoids letting [09_OS_MASTER_PLAN.md](docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md) act as shadow implementation authority

This plan is the active execution authority for the ControlPlane lane.
[09_OS_MASTER_PLAN.md](docs/projects/ControlPlane/orket_control_plane_packet/09_OS_MASTER_PLAN.md) remains architecture direction and planning rationale only.

## Source authorities

1. [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)
2. [00_CONTROL_PLANE_FOUNDATION_PACKET.md](docs/projects/ControlPlane/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md)
3. [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
4. [00B_CURRENT_STATE_CROSSWALK.md](docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md)
5. [01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md)
6. [02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md)
7. [03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md)
8. [04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md)
9. [05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md)
10. [06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md)
11. [07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md)
12. [08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md)
13. [10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md)
14. [11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
15. [12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/projects/ControlPlane/orket_control_plane_packet/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)
16. [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
17. [CURRENT_AUTHORITY.md](CURRENT_AUTHORITY.md)

## Decision lock

Implementation must not start without the following locked decisions remaining frozen:

1. `Reservation` is first-class.
2. `FinalTruthRecord` is first-class.
3. `recovering` means control-plane recovery activity, not ordinary workload execution.
4. Resumed or replacement workload execution returns to `executing`.
5. `mark_terminal` may stop continuation but may not rewrite truth classification.
6. Operator risk acceptance is never world-state evidence.
7. Operator attestation is bounded, explicit, and never equivalent to adapter observation.
8. The effect journal is a normative authority surface, not mere storage.
9. Resolved policy and configuration snapshots are durable objects, not just digests.
10. A slim namespace contract exists now even if richer namespace work comes later.

## Current truth

The current runtime has useful partial seams but not a unified control plane.

The strongest current anchors are:
1. run-start and run-summary artifacts
2. sandbox lifecycle, reconciliation, and cleanup services
3. control-plane contract, publication, and persistence seams in `core`, `application`, and storage adapters
4. sandbox execution now publishes supervisor-owned `RunRecord` and `AttemptRecord` on the default orchestrator path, including waiting, reacquire, and terminal closure transitions
5. sandbox terminal closure now partially publishing first-class `FinalTruthRecord` through workflow, policy, and lifecycle terminal-outcome paths
6. sandbox `lost_runtime` reconciliation now partially publishing durable `ReconciliationRecord` plus reconciliation-closed final truth
7. sandbox lifecycle now partially publishes first-class `LeaseRecord` history across initial claim, activation, renewal, reclaimable expiry, lost-runtime uncertainty, and verified cleanup on the default orchestrator path
8. the Gitea state worker path now publishes one lease-backed `RunRecord` per claimed card and lease epoch, a first-class claim `ReservationRecord` after backend lease acquire with promotion only after the initial `ready -> in_progress` claim transition succeeds and invalidation on claim-stage failure, one pre-effect `resume_forbidden` `CheckpointRecord` plus `CheckpointAcceptanceRecord` from the claimed-card observation, one first-class `AttemptRecord`, worker-owned claim/finalize `StepRecord` entries plus a failed claim step when the initial claim mutation fails, transition-scoped `EffectJournalEntryRecord` history for observed state transitions, claim-scope `ReconciliationRecord` publication for failed initial claim mutations, terminal `RecoveryDecisionRecord` closure for lease-expiry, claim-transition failure, and runtime-failure stop cases, terminal `FinalTruthRecord` closure, and first-class `LeaseRecord` history for non-sandbox card processing including claim-failure `lease_uncertain` publication on the default state-backend worker path
9. sandbox create now publishes a first-class `ReservationRecord` for allocation truth and promotes it explicitly to lease authority on lifecycle record creation
10. sandbox deploy and verified cleanup now publish first-class `EffectJournalEntryRecord` history on the default orchestrator path
11. sandbox recovery and terminal execution now publish durable `RecoveryDecisionRecord` entries for checkpoint-backed new-attempt reacquire and terminal-stop decisions on the default orchestrator path, with reclaimable reacquire decisions targeting the accepted checkpoint directly when reclaimable checkpoint truth exists
12. explicit authenticated sandbox stop now publishes a durable `OperatorActionRecord` with a non-secret operator actor fingerprint on the default API-to-orchestrator path
13. approval-gated admission now publishes a first-class `ReservationRecord` with `operator_hold_reservation` semantics for repo-backed tool-approval requests, guard-review pending-gate requests, and governed kernel approvals, and resolves that reservation on approval decision, with approval list and detail surfaces exposing the latest reservation summary when present
14. explicit authenticated tool-approval resolutions now publish durable `OperatorActionRecord` entries on the default API-to-engine approval path, with grants recorded as operator risk acceptance and denials or expirations recorded as terminal commands, supported guard-review pending-gate resolutions now publishing durable `approve_continue` or `mark_terminal` commands on the pending-gate target, approval list/detail surfaces exposing the latest control-plane operator-action summary for each approval request including `command_class`, affected transition refs, and affected resource refs plus `control_plane_target_ref`, the latest target-side run and attempt summary when durable execution truth exists including namespace scope, admission decision receipt, policy snapshot id, configuration snapshot id, creation timestamp, and attempt count, the latest target-side step summary including namespace scope, capability used, output ref, resources touched, and receipt refs, checkpoint summary including creation timestamp, invalidation and dependency detail, policy digest, integrity verification ref, required reobservation class, snapshot ref, and acceptance decision or supervisor or dependency detail, and effect-journal summary including latest step id, publication sequence, intended target, observed result ref, authorization-basis ref, publication timestamp, integrity verification ref, prior-linkage, contradiction or supersession refs, entry digest, and uncertainty when durable target truth exists, the latest target-side operator action summary including receipt refs, the latest target-side reservation summary including reservation kind, invalidation basis, supervisor authority, and promotion linkage, and the latest target-side final-truth summary including fuller classifications, authoritative result ref, and authority sources when present, orchestrator-generated tool-approval payloads allowing supported tool-approval decisions to publish a second operator action on the governed turn-tool run target when `control_plane_target_ref` is present, governed kernel approvals now recovering that governed target from authoritative approval-reservation truth even when the nervous-system payload omits it, and non-tool pending gates now failing closed instead of being mislabeled as tool-approval operator actions
15. sandbox operator views now surface control-plane run state, current attempt state, reservation and lease status, fuller final-truth classifications including result, closure basis, terminality basis, evidence sufficiency, residual uncertainty, degradation, authoritative result ref, and authority sources, latest effect-journal intended target, observed result ref, authorization-basis ref, integrity verification ref, and uncertainty classification, latest operator command summary including receipt refs, and the latest reconciliation id, divergence class, and safe-continuation class on the default orchestrator path
16. sandbox lease-expiry reconciliation now publishes live `CheckpointRecord` and `CheckpointAcceptanceRecord` entries backed by immutable lifecycle snapshots on the default orchestrator path, with `resume_new_attempt_from_checkpoint` semantics and operator views surfacing checkpoint id, resumability class, and acceptance outcome
17. the authenticated kernel action API path now publishes one governed control-plane run per `session_id + trace_id`, one initial attempt, one commit-scoped `StepRecord` for observed or claimed commit execution, commit-driven `EffectJournalEntryRecord` truth for committed actions with execution-result evidence, preserved effect truth for policy-rejected actions when execution was actually observed, and terminal `FinalTruthRecord` closure on commit or session end
18. authenticated kernel session-end now publishes a durable `OperatorActionRecord` with `cancel_run` command semantics when it terminally cancels a governed kernel-action run
19. kernel action replay and audit API surfaces now expose a control-plane summary containing run state, attempt state, latest reservation summary including invalidation basis and supervisor authority, step count, latest step including namespace scope, resources touched, and receipt refs, fuller final-truth classifications including degradation, terminality basis, authoritative result ref, and authority sources, effect count, and latest operator action including receipt refs for governed kernel-action traces
20. the default governed turn-tool path now publishes one governed run per `session_id + issue_id + role + turn_index`, one initial attempt, a pre-effect `resume_new_attempt_from_checkpoint` `CheckpointRecord` plus `CheckpointAcceptanceRecord` backed by an immutable checkpoint snapshot artifact before tool execution begins, supervisor-owned `RecoveryDecisionRecord` publication plus replacement-attempt bootstrap when `resume_mode` resumes an unfinished pre-effect governed turn, explicit reconciliation-record publication plus `require_reconciliation_then_decide` recovery authority and immediate reconciliation-rationalized terminal closeout when `resume_mode` encounters unfinished post-effect or effect-boundary-uncertain governed execution, one `StepRecord` per executed `operation_id`, `EffectJournalEntryRecord` truth for governed tool operations, terminal `terminate_run` recovery decisions with checkpoint/effect preconditions and blocked continuation actions plus `FinalTruthRecord` closure for blocked pre-effect, failed post-effect, and reconciliation-closed unsafe resume cases across both protocol and non-protocol turns, completed governed re-entry that reuses durable step and operation artifacts before prompt/model execution and before checkpoint artifact rewrite rather than rerunning the model and only reusing finalized step or effect truth later, fail-closed re-entry on terminal or recovery-blocked governed runs before model invocation and checkpoint artifact rewrite, and an explicit default `issue:<issue_id>` namespace with fail-closed scope enforcement on governed tool bindings and invocation manifests
21. the standalone coordinator API now publishes first-class non-hedged `ReservationRecord` truth for claim admission with explicit promotion to lease authority, first-class `LeaseRecord` history for claim, renew, expiry-before-reclaim, open-cards expiry observation, and release transitions on the default coordinator surface, and latest reservation and lease summaries on list, claim, renew, complete, and fail responses including reservation kind, reservation basis, reservation supervisor authority, promotion rule, lease resource id, lease expiry basis, lease cleanup eligibility rule, granted timestamp, publication timestamp, and last confirmed observation

The highest-risk missing areas are:
1. reservation truth now covers sandbox allocation, approval-gated operator holds for repo-backed tool approvals, guard-review pending gates, and governed kernel approvals, non-hedged coordinator claim admission, and Gitea worker claim admission, but it is still not wired into general admission and scheduling
2. final-truth and reconciliation publication are still partial across closure paths outside sandbox workflow, policy, lifecycle terminal outcomes, `lost_runtime`, the governed kernel action API path, and the governed turn-tool path
3. operator-action truth is still fragmented outside explicit authenticated sandbox stop, authenticated kernel session-end cancel, tool-approval resolution publication, and broader attestation or non-sandbox operator surfaces
4. lease truth is no longer sandbox-only, and the standalone coordinator API plus the Gitea worker path now publish non-sandbox lease history linked to explicit claim reservations, but it is still not shared by admission, scheduling, or most non-sandbox runtime paths
5. effect-journal publication is still limited to sandbox deploy, verified cleanup, governed kernel-action commit behavior, governed turn-tool execution, and Gitea worker state transitions rather than broader workload and tooling execution
6. same-attempt checkpoint resume and broader supervisor-owned checkpoint creation still are not live on runtime execution paths beyond sandbox reclaimable checkpoint-backed new-attempt recovery, governed turn execution's pre-effect checkpoint-backed new-attempt recovery boundary, and the Gitea worker path's pre-effect `resume_forbidden` checkpoint boundary
7. namespace and safe-tooling gates are now live on the governed turn-tool path, but broader runtime tooling, workload composition, and resource targeting still do not share one explicit namespace authority surface

Implementation slices must reference [00B_CURRENT_STATE_CROSSWALK.md](docs/projects/ControlPlane/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md) to name what current surface is being promoted, replaced, or declared missing.

## Workstream A - Control-plane contract types and snapshot objects

Objective:
1. land the canonical code-level contract family for control-plane nouns, enums, and durable snapshot objects

Required deliverables:
1. code-level enum and object definitions matching [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
2. first-class `Reservation`
3. first-class `FinalTruthRecord`
4. durable resolved policy snapshot object
5. durable resolved configuration snapshot object

Acceptance criteria:
1. code imports one canonical enum family instead of re-encoding packet vocab in multiple modules
2. `Run`, `RecoveryDecision`, and `FinalTruthRecord` are representable without ad hoc free-text fields
3. snapshot objects can support audit and replay without reconstructing source state after the fact

Proof target:
1. contract
2. unit

## Workstream B - Supervisor state machine and guard enforcement

Objective:
1. replace loop-shaped execution truth with explicit supervisor-owned run and attempt transitions

Required deliverables:
1. run and attempt state machines enforcing the canonical lifecycle
2. guard and action enforcement for the risky boundaries locked in the packet
3. explicit `reconciling` versus `recovering` behavior
4. transition receipts and structured rejection surfaces

Acceptance criteria:
1. illegal transitions fail closed
2. resumed or replacement execution returns to `executing`
3. `recovering` is used only for control-plane recovery activity
4. operator-blocked and quarantined paths are distinguishable in code and proof

Proof target:
1. unit
2. contract
3. integration

## Workstream C - Reservation, lease, and admission truth

Objective:
1. make admission and scheduling publish durable reservation truth and explicit reservation-to-lease progression

Required deliverables:
1. reservation object family and persistence
2. admission output publication carrying reservation references
3. reservation expiry, invalidation, and release rules
4. lease promotion rules under supervisor control
5. cancellation and failure handling for reservations and leases

Acceptance criteria:
1. admission no longer publishes undefined reservation nouns
2. concurrency and resource claims are durable and auditable
3. exclusive ownership promotes to lease explicitly rather than by implication

Proof target:
1. contract
2. integration

## Workstream D - Effect journal, checkpoint, and recovery-decision authority

Objective:
1. land the authority surfaces that recovery and reconciliation already depend on

Required deliverables:
1. normative effect journal implementation
2. ordered journal publication with integrity checks
3. checkpoint admissibility and invalidation logic
4. recovery-decision objects that can authorize:
   1. control-plane recovery actions
   2. checkpoint resume
   3. new attempt start
5. final-truth publication inputs from recovery, reconciliation, and journal surfaces

Acceptance criteria:
1. effect truth is published through a journal, not inferred from scattered receipts
2. checkpoints do not imply resumability without supervisor acceptance
3. recovery decisions can distinguish resumed execution from new-attempt execution

Proof target:
1. contract
2. integration

## Workstream E - Namespace and safe-tooling enforcement

Objective:
1. prevent resources, tool visibility, and child workload composition from remaining ambient or implicit

Required deliverables:
1. slim namespace object or contract family
2. namespace-aware reservation, lease, and capability targeting
3. safe-tooling invocation contracts tied to run, attempt, step, and effect publication
4. degraded-mode tool restrictions
5. child-workload composition rules that preserve supervisor authority

Acceptance criteria:
1. shared versus private resource boundaries are explicit
2. undeclared capability or namespace escalation fails closed
3. tool invocation cannot bypass effect-journal or operator-gate rules

Proof target:
1. contract
2. integration

## Workstream F - Reconciliation, operator, and closure truth

Objective:
1. finish the control plane by making recovery, operator action, and run closure publish one coherent truth surface

Required deliverables:
1. reconciliation records with divergence and continuation classes
2. operator input split between command, risk acceptance, and attestation
3. final-truth publication path producing first-class `FinalTruthRecord`
4. operator command handling where terminality can change without rewriting truth

Acceptance criteria:
1. operator risk acceptance never satisfies evidence requirements
2. operator attestation remains visibly distinct from adapter observation
3. final-truth publication carries result, evidence sufficiency, residual uncertainty, degradation, and closure basis

Proof target:
1. contract
2. integration
3. live where a real external or sandbox path is involved

## Verification plan

Structural proofs required:
1. lifecycle legality and illegal-transition rejection
2. reservation-to-lease progression
3. effect journal ordering and integrity enforcement
4. checkpoint invalidation and admissibility
5. reconciliation divergence classification
6. final-truth publication invariants

Live proofs required where the implementation touches real external or sandbox behavior:
1. pre-effect failure with truthful retry handling
2. effect-boundary uncertainty forcing reconcile-or-stop
3. false completion claim rejected from final truth
4. orphan or stale lease handling after interruption
5. operator-approved degraded continuation remaining visibly degraded

## Stop conditions

1. Stop and narrow scope if the lane starts inventing a second control-plane vocabulary outside [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).
2. Stop and narrow scope if an implementation slice cannot name its current-state crosswalk row.
3. Stop and split the lane if namespace work turns into a full multitenant platform redesign.
4. Stop and split the lane if tooling integration attempts to bypass the effect journal or supervisor.

## Execution order

1. land contract types and durable snapshot objects
2. land supervisor state and guard enforcement
3. land reservation and lease truth
4. land effect journal, checkpoint, and recovery-decision authority
5. land namespace and safe-tooling gates
6. land reconciliation, operator, and final-truth publication

## Completion gate

This lane is complete only when:
1. packet vocab is implemented through one canonical code-level authority
2. run closure publishes first-class `FinalTruthRecord`
3. reservation and lease truth are explicit and durable
4. recovery and reconciliation consume journal and checkpoint truth directly
5. operator actions can affect terminality without rewriting truth
6. code, docs, and proofs tell the same story
