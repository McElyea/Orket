# Control-Plane Implementation Plan
Last updated: 2026-03-26
Status: Completed (archived lane closeout authority)
Owner: Orket Core
Lane type: Archived implementation plan
Source contract index: [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)

## Objective

Turn the accepted ControlPlane packet v2 into an implementation-sequenced lane that:
1. lands canonical control-plane contracts first
2. keeps current-state migration honest
3. avoids letting [09_OS_MASTER_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/09_OS_MASTER_PLAN.md) act as shadow implementation authority

This plan was the active execution authority for the ControlPlane lane.
[09_OS_MASTER_PLAN.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/09_OS_MASTER_PLAN.md) remains architecture direction and planning rationale only.

## Source authorities

1. [docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md](docs/specs/CONTROL_PLANE_PACKET_V1_INDEX.md)
2. [00_CONTROL_PLANE_FOUNDATION_PACKET.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00_CONTROL_PLANE_FOUNDATION_PACKET.md)
3. [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
4. [00B_CURRENT_STATE_CROSSWALK.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md)
5. [01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md](docs/specs/01_EXECUTION_OBJECT_MODEL_REQUIREMENTS.md)
6. [02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md](docs/specs/02_WORKLOAD_LIFECYCLE_AND_SUPERVISION_REQUIREMENTS.md)
7. [03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md](docs/specs/03_FAILURE_TAXONOMY_AND_RECOVERY_REQUIREMENTS.md)
8. [04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md](docs/specs/04_CAPABILITY_AND_EFFECT_MODEL_REQUIREMENTS.md)
9. [05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md](docs/specs/05_RESOURCE_LEASE_AND_OWNERSHIP_REQUIREMENTS.md)
10. [06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md](docs/specs/06_RECONCILIATION_AUTHORITY_REQUIREMENTS.md)
11. [07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md](docs/specs/07_OPERATOR_CONTROL_SURFACE_REQUIREMENTS.md)
12. [08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md](docs/specs/08_MINIMAL_ADMISSION_AND_SCHEDULING_REQUIREMENTS.md)
13. [10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md](docs/specs/10_EFFECT_JOURNAL_AND_CHECKPOINT_REQUIREMENTS.md)
14. [11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md](docs/specs/11_NAMESPACE_AND_WORKLOAD_COMPOSITION_REQUIREMENTS.md)
15. [12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md](docs/specs/12_SAFE_TOOLING_WORKLOAD_INTEGRATION_REQUIREMENTS.md)
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
8. the Gitea state worker path now publishes one lease-backed `RunRecord` per claimed card and lease epoch, a first-class claim `ReservationRecord` after backend lease acquire with promotion only after the initial `ready -> in_progress` claim transition succeeds plus fail-closed promotion rollback that invalidates unpromoted reservation truth and releases just-published active lease authority when promotion fails, one pre-effect `resume_forbidden` `CheckpointRecord` plus `CheckpointAcceptanceRecord` from the claimed-card observation, one first-class `AttemptRecord`, worker-owned claim/finalize `StepRecord` entries plus a failed claim step when the initial claim mutation fails, transition-scoped `EffectJournalEntryRecord` history for observed state transitions, claim-scope `ReconciliationRecord` publication for failed initial claim mutations, terminal `RecoveryDecisionRecord` closure for lease-expiry, claim-transition failure, and runtime-failure stop cases, terminal `FinalTruthRecord` closure, and first-class `LeaseRecord` history for non-sandbox card processing including claim-failure `lease_uncertain` publication on the default state-backend worker path
9. sandbox create now publishes a first-class `ReservationRecord` for allocation truth and promotes it explicitly to lease authority on lifecycle record creation, with fail-closed create-record rollback that releases just-published active lease authority and invalidates the unpromoted reservation if lifecycle record creation fails after lease publication
10. sandbox deploy and verified cleanup now publish first-class `EffectJournalEntryRecord` history on the default orchestrator path
11. sandbox recovery and terminal execution now publish durable `RecoveryDecisionRecord` entries for checkpoint-backed new-attempt reacquire and terminal-stop decisions on the default orchestrator path, with reclaimable reacquire decisions targeting the accepted checkpoint directly when reclaimable checkpoint truth exists
12. explicit authenticated sandbox stop, session-halt, and interaction-cancel API paths now publish durable `OperatorActionRecord` `cancel_run` commands with non-secret operator actor fingerprints on the default API-to-orchestrator and API-to-engine control surfaces
13. approval-gated admission now publishes a first-class `ReservationRecord` with `operator_hold_reservation` semantics for repo-backed tool-approval requests, guard-review pending-gate requests, and governed kernel approvals, and resolves that reservation on approval decision, with approval list and detail surfaces exposing the latest reservation summary when present
14. explicit authenticated tool-approval resolutions now publish durable `OperatorActionRecord` entries on the default API-to-engine approval path, with grants recorded as operator risk acceptance and denials or expirations recorded as terminal commands, supported guard-review pending-gate resolutions now publishing durable `approve_continue` or `mark_terminal` commands on the pending-gate target, approval list/detail surfaces exposing the latest control-plane operator-action summary for each approval request including `command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, `precondition_basis_ref`, affected transition refs, and affected resource refs plus `control_plane_target_ref`, the latest target-side run and attempt summary when durable execution truth exists including namespace scope, admission decision receipt, policy snapshot id, configuration snapshot id, creation timestamp, and attempt count, the latest target-side step summary including namespace scope, capability used, output ref, resources touched, and receipt refs, checkpoint summary including creation timestamp, invalidation and dependency detail, policy digest, integrity verification ref, required reobservation class, snapshot ref, and acceptance decision or supervisor or dependency detail, and effect-journal summary including latest step id, publication sequence, intended target, observed result ref, authorization-basis ref, publication timestamp, integrity verification ref, prior-linkage, contradiction or supersession refs, entry digest, and uncertainty when durable target truth exists, the latest target-side operator action summary including receipt refs, the latest target-side reservation summary including reservation kind, invalidation basis, supervisor authority, and promotion linkage, and the latest target-side final-truth summary including fuller classifications, authoritative result ref, and authority sources when present, orchestrator-generated tool-approval payloads allowing supported tool-approval decisions to publish a second operator action on the governed turn-tool run target when `control_plane_target_ref` is present, governed kernel approvals now recovering that governed target from authoritative approval-reservation truth even when the nervous-system payload omits it, and non-tool pending gates now failing closed instead of being mislabeled as tool-approval operator actions
15. sandbox operator views now surface control-plane run state, current attempt state, reservation and lease status, fuller final-truth classifications including result, closure basis, terminality basis, evidence sufficiency, residual uncertainty, degradation, authoritative result ref, and authority sources, latest effect-journal intended target, observed result ref, authorization-basis ref, integrity verification ref, and uncertainty classification, latest operator command summary including receipt refs, and the latest reconciliation id, divergence class, and safe-continuation class on the default orchestrator path
16. sandbox lease-expiry reconciliation now publishes live `CheckpointRecord` and `CheckpointAcceptanceRecord` entries backed by immutable lifecycle snapshots on the default orchestrator path, with `resume_new_attempt_from_checkpoint` semantics and operator views surfacing checkpoint id, resumability class, and acceptance outcome
17. the authenticated kernel action API path now publishes one governed control-plane run per `session_id + trace_id`, one initial attempt, a first-class admission `ReservationRecord` with explicit promotion to an active execution `LeaseRecord` only when commit-time execution is committed or observed plus fail-closed activation rollback that invalidates unpromoted reservation truth and releases any just-published active execution lease when promotion fails, explicit default `session:<session_id>` namespace scope authority for governed kernel runs with fail-closed rejection of broader proposal/request namespace-scope declarations and commit-step namespace truth publication, truthful reservation-only closure for pre-effect terminal policy rejection without observed execution, fail-closed guarded commit-status publication that rejects unsupported status tokens before lifecycle truth mutation, admit/commit/session-end response control-plane references (`control_plane_run_id`, `control_plane_attempt_id`, `control_plane_attempt_state`, plus reservation/lease/final-truth refs when present, plus recovery decision/action refs and latest operator-action id when present) after durable publication, commit-scoped `StepRecord` truth for observed or claimed commit execution, commit-driven `EffectJournalEntryRecord` truth for committed actions with execution-result evidence, preserved effect truth for policy-rejected actions when execution was actually observed, explicit terminal `terminate_run` `RecoveryDecisionRecord` authority for both observed post-effect policy-rejected/error outcomes and non-observed pre-effect policy-rejected/error outcomes with corresponding attempt boundary taxonomy, explicit terminal execution-lease release on commit closeout, unpromoted reservation release on session-end cancellation and reservation-only closeout paths, terminalization of any non-terminal session attempt as `abandoned` before run cancellation, and terminal `FinalTruthRecord` closure on commit or session end
18. authenticated kernel session-end now publishes a durable `OperatorActionRecord` with `cancel_run` command semantics when it terminally cancels a governed kernel-action run and, when explicitly requested on the authenticated API path, now publishes a second durable `operator_attestation` action for the same run with bounded attestation scope plus payload instead of collapsing that operator input into command or risk-acceptance truth
19. kernel action replay and audit API surfaces now expose a control-plane summary containing run state, attempt state, current attempt failure boundary plus taxonomy and recovery action summary when present, latest reservation summary including invalidation basis and supervisor authority for both approval-hold and run-owned admission reservations with promoted run-owned execution reservations taking precedence over stale terminal hold records, latest execution-lease summary when present, step count, latest step including namespace scope, resources touched, and receipt refs, fuller final-truth classifications including degradation, terminality basis, authoritative result ref, and authority sources, effect count, and latest operator action including receipt refs plus explicit `input_class` split details (`command_class`, `risk_acceptance_scope`, `attestation_scope`, `attestation_payload`, and `precondition_basis_ref`) for governed kernel-action traces
20. the default governed turn-tool path now publishes one governed run per `session_id + issue_id + role + turn_index`, one initial attempt, a first-class issue-scoped namespace `ReservationRecord` on governed admission with explicit promotion to an active execution `LeaseRecord` on execution start plus fail-closed activation rollback that invalidates unpromoted reservation truth and releases just-published active execution lease authority when promotion fails, a pre-effect `resume_same_attempt` `CheckpointRecord` plus `CheckpointAcceptanceRecord` backed by an immutable checkpoint snapshot artifact before tool execution begins with explicit dependent reservation/lease refs, supervisor-owned `RecoveryDecisionRecord` publication for same-attempt checkpoint recovery when `resume_mode` resumes an unfinished pre-effect governed turn on the current attempt, safe pre-effect `resume_mode` continuation that now consumes the accepted checkpoint snapshot before prompt/model work and continues on the current attempt instead of bootstrapping attempt 2 while failing closed if immutable snapshot identity drifts from the current run or namespace request, truthful continued consumption of older governed `resume_new_attempt_from_checkpoint` lineage when those records already exist, explicit reconciliation-record publication plus `require_reconciliation_then_decide` recovery authority and immediate reconciliation-rationalized terminal closeout when `resume_mode` encounters unfinished post-effect or effect-boundary-uncertain governed execution, already-dirty same-attempt or replacement-attempt truth, or durable operation artifacts without matching step/effect authority, one `StepRecord` per executed `operation_id`, `EffectJournalEntryRecord` truth for governed tool operations, explicit execution-lease release on governed closeout, terminal `terminate_run` recovery decisions with checkpoint/effect preconditions and blocked continuation actions plus `FinalTruthRecord` closure for blocked pre-effect, failed post-effect, and reconciliation-closed unsafe resume cases across both protocol and non-protocol turns, preflight terminal closeout now materializing an initial attempt when missing, abandoning any non-terminal attempt with explicit `pre_effect_failure` taxonomy plus terminal recovery-decision authority before run terminal state publication, and releasing promoted execution authority when that closeout occurs after execution start, completed governed re-entry that now requires accepted checkpoint authority plus immutable checkpoint snapshot identity, durable step plus effect plus operation alignment, and no unexpected operation artifacts before reusing artifacts ahead of prompt/model execution and ahead of checkpoint artifact rewrite rather than rerunning the model and only reusing finalized step or effect truth later, fail-closed re-entry on terminal or recovery-blocked governed runs before model invocation and checkpoint artifact rewrite, and an explicit default `issue:<issue_id>` namespace with fail-closed scope enforcement on governed tool bindings and invocation manifests
21. the standalone coordinator API now publishes first-class non-hedged `ReservationRecord` truth for claim admission with explicit promotion to lease authority plus fail-closed promotion rollback that invalidates unpromoted reservation truth and releases just-published active lease authority when promotion fails, first-class `LeaseRecord` history for claim, renew, expiry-before-reclaim, open-cards expiry observation, and release transitions on the default coordinator surface, and latest reservation and lease summaries on list, claim, renew, complete, and fail responses including reservation kind, reservation basis, reservation supervisor authority, promotion rule, lease resource id, lease expiry basis, lease cleanup eligibility rule, granted timestamp, publication timestamp, and last confirmed observation
22. the default orchestrator issue-dispatch path now publishes one first-class control-plane run and attempt per `session_id + issue_id + seat + turn_index`, a concurrency reservation for the active issue dispatch slot with explicit promotion to a lease on dispatch start, fail-closed dispatch-start authority rollback that invalidates unpromoted reservation truth and releases any just-published active dispatch lease when promotion fails, fail-closed reused-run rejection when dispatch run ids collide with still-active lifecycle truth or with non-terminal attempt drift under terminal run truth, fail-closed namespace-scope drift rejection for reused closed runs and active closeout paths, fail-closed reused-run reservation or lease drift rejection when closed dispatch runs still carry active resource authority or lack promoted-to-lease lineage, fail-closed closeout rejection when an active dispatch run no longer carries promoted reservation plus active lease authority, a dispatch step plus effect-journal entry for turn-start status mutation, a closeout step plus effect-journal entry for both transition-based and observation-only closeouts, terminal final-truth plus lease release on later issue transitions or on successful observed-status closeout when no later issue transition occurs, terminal `RecoveryDecisionRecord` authority for failed or blocked dispatch closeouts, and fail-closed closeout rejection when an active dispatch reservation points at terminal attempt drift, while scheduler-owned issue transitions that happen without an active dispatch run now publish one first-class namespace-scoped run and attempt, a namespace reservation with explicit promotion to a lease, fail-closed namespace-activation rollback that invalidates unpromoted reservation truth and releases any just-published active namespace lease when promotion fails, fail-closed non-terminal reused-run rejection when scheduler mutation run ids collide with still-active lifecycle truth or with non-terminal attempt drift under terminal run truth, fail-closed namespace-scope drift rejection for reused closed mutation runs, fail-closed reused-run reservation or lease drift rejection when closed scheduler mutation runs still carry active resource authority or lack promoted-to-lease lineage, a scheduler mutation step, an effect-journal entry, terminal final-truth, and terminal `RecoveryDecisionRecord` authority for failed or blocked closeouts for dependency-block propagation, pre-dispatch retry or terminal issue mutations, execution-pipeline resume requeue of stalled issues, and targeted execution-pipeline issue-resume requeue, and team-replan child issue creation now publishes the same namespace reservation, lease, step, effect, and final-truth family for the child workload-composition mutation via `orket/application/services/orchestrator_issue_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_service.py`, `orket/application/services/orchestrator_scheduler_control_plane_mutation.py`, `orket/application/workflows/orchestrator_ops.py`, and `orket/runtime/execution_pipeline.py`
23. the canonical control-plane contract model family now fails closed on unsupported record `contract_version` while preserving snapshot schema-version enforcement, keeping packet-v2 enum-backed nouns and first-class record objects pinned to one authority surface via `orket/core/contracts/control_plane_models.py`, `orket/core/domain/control_plane_enums.py`, `tests/contracts/test_control_plane_contract_schema.py`, and `tests/contracts/test_control_plane_contract_version_matrix.py`

The highest-risk missing areas are:
1. reservation truth now covers sandbox allocation, approval-gated operator holds for repo-backed tool approvals, guard-review pending gates, governed kernel approvals, default orchestrator issue dispatch, default orchestrator scheduler-owned issue mutation and team-replan child issue composition, execution-pipeline resume requeue and targeted issue-resume scheduler transitions, non-hedged coordinator claim admission, and Gitea worker claim admission, but it is still not wired into all admission and scheduling paths
2. final-truth and reconciliation publication are still partial across closure paths outside sandbox workflow, policy, lifecycle terminal outcomes, `lost_runtime`, the governed kernel action API path, and the governed turn-tool path
3. operator-action truth is still fragmented outside explicit authenticated sandbox stop, authenticated session halt, authenticated interaction cancel, authenticated kernel session-end command plus attestation publication, tool-approval resolution publication, and broader non-sandbox operator surfaces
4. lease truth is no longer sandbox-only, and the standalone coordinator API plus the Gitea worker path now publish non-sandbox lease history linked to explicit claim reservations while the default orchestrator scheduler-owned issue mutation path now publishes namespace lease history for no-dispatch issue transitions and child issue creation, but it is still not shared by admission, scheduling, or most non-sandbox runtime paths
5. effect-journal publication is still limited to sandbox deploy, verified cleanup, default orchestrator issue dispatch (including observation-only closeout) plus scheduler-owned issue mutation and team-replan child issue creation, governed kernel-action commit behavior, governed turn-tool execution, and Gitea worker state transitions rather than broader workload and tooling execution
6. broader supervisor-owned checkpoint creation still is not live on runtime execution paths beyond sandbox reclaimable checkpoint-backed new-attempt recovery, governed turn execution's pre-effect same-attempt checkpoint boundary, and the Gitea worker path's pre-effect `resume_forbidden` checkpoint boundary
7. namespace and safe-tooling gates are now live on the default turn-tool path across both protocol and non-protocol turns, the authenticated kernel-action path now enforces fail-closed `session:<session_id>` namespace scope authority for governed runs and commit-step truth, and default orchestrator issue-dispatch plus scheduler-owned mutation and team-replan child issue creation paths now publish explicit issue-scoped namespace reservation and lease authority with fail-closed namespace-scope drift rejection on reused-run and closeout checks, but broader runtime tooling, workload composition, scheduling, and resource targeting still do not share one explicit namespace authority surface

Implementation slices must reference [00B_CURRENT_STATE_CROSSWALK.md](docs/projects/archive/ControlPlane/CP04092026-PROJECT-CLOSEOUT/orket_control_plane_packet/00B_CURRENT_STATE_CROSSWALK.md) to name what current surface is being promoted, replaced, or declared missing.

## Workstream A - Control-plane contract types and snapshot objects

Objective:
1. land the canonical code-level contract family for control-plane nouns, enums, and durable snapshot objects

Required deliverables:
1. code-level enum and object definitions matching [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md)
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

1. Stop and narrow scope if the lane starts inventing a second control-plane vocabulary outside [00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md](docs/specs/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md).
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

## Completion assessment (2026-03-26)

Lane closeout status: implementation complete for the accepted packet-v2 scope and archived with roadmap closeout.

Workstream progress:
1. Workstream A: closed; complete in code and proof for accepted packet-v2 contract authority, including canonical enum-backed contract families with fail-closed record `contract_version` enforcement (explicit rejection proofs for run, reservation, and final-truth records plus matrix proof that all first-class record models pin to one contract-version default), and durable resolved policy/configuration snapshots on active run-init paths with explicit governed turn-tool begin-execution and preflight-terminal-closeout snapshot proof coverage.
2. Workstream B: closed; complete in code and proof for the currently integrated canonical control-plane surfaces, with supervisor lifecycle and guard enforcement failing closed on unsupported governed-kernel commit status, governed-kernel reused-run drift (missing current attempt, missing terminal final truth, and terminal or active run-attempt mismatch), governed turn preflight terminal-closeout boundary enforcement with initial-attempt materialization, default issue-dispatch reused-run and closeout attempt-drift collisions, and scheduler-owned reused-run collisions when mutation run ids point at still-active lifecycle truth or non-terminal attempt drift under terminal run truth.
3. Workstream C: closed; complete in code and proof for the currently integrated canonical control-plane surfaces, with reservation and lease authority durable across the main sandbox, governed kernel-action, governed turn-tool, default orchestrator issue-dispatch, scheduler-owned mutation, execution-pipeline resume requeue and targeted issue-resume scheduling, standalone coordinator claim, approval-gated hold, and Gitea worker claim surfaces, including fail-closed promotion rollback coverage and reused-run reservation or lease drift rejection coverage on integrated paths.
4. Workstream D: closed; complete in code and proof for the currently integrated canonical control-plane surfaces, with effect-journal, checkpoint, and recovery-decision authority covering canonical failure-taxonomy publication and terminal recovery-decision publication on integrated governed-turn plus issue-dispatch plus scheduler-mutation closeouts, including observation-only closeout journal publication on the default issue-dispatch path.
5. Workstream E: closed; complete in code and proof for the currently integrated canonical control-plane surfaces, with namespace and safe-tooling fail-closed enforcement spanning governed turn-tool (`issue:<issue_id>`), governed kernel-action (`session:<session_id>`), and default orchestrator issue-dispatch plus scheduler-owned mutation paths with explicit issue-scoped namespace authority and namespace-drift rejection on reused-run and active closeout checks.
6. Workstream F: closed; complete in code, structural proof, and live proof for the currently integrated and externally exercised control-plane surfaces. Reconciliation and final-truth publication now pair with explicit operator input split publication (command, risk acceptance, and attestation) on integrated approval and authenticated kernel session-end paths, authenticated session halt plus interaction-cancel controls publish durable `cancel_run` command truth on their runtime control surfaces, and read-model surfaces preserve the input split explicitly instead of collapsing attestation into command or observation summaries. Live closeout proof now passes across the full `tests/live` suite with sandbox disabled for routine proof (`24 passed, 5 skipped`, `2026-03-26`).

Blocking gaps before lane completion:
1. none for the accepted packet-v2 scope in this lane.

## Completion gate

This lane is complete only when:
1. packet vocab is implemented through one canonical code-level authority
2. run closure publishes first-class `FinalTruthRecord`
3. reservation and lease truth are explicit and durable
4. recovery and reconciliation consume journal and checkpoint truth directly
5. operator actions can affect terminality without rewriting truth
6. code, docs, and proofs tell the same story
