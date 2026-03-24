# Control-Plane Implementation Plan
Last updated: 2026-03-23
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
4. sandbox terminal closure now partially publishing first-class `FinalTruthRecord` through workflow, policy, and lifecycle terminal-outcome paths
5. sandbox `lost_runtime` reconciliation now partially publishing durable `ReconciliationRecord` plus reconciliation-closed final truth
6. sandbox lifecycle now partially publishes first-class `LeaseRecord` history across initial claim, activation, renewal, reclaimable expiry, lost-runtime uncertainty, and verified cleanup on the default orchestrator path

The highest-risk missing areas are:
1. reservation truth is not yet wired into admission and scheduling
2. run and attempt records are not yet supervisor-owned durable runtime authorities
3. final-truth and reconciliation publication are still partial across closure paths outside sandbox workflow, policy, lifecycle terminal outcomes, and `lost_runtime`
4. recovery-decision and operator-action truth are still fragmented in live runtime behavior
5. lease truth is still sandbox-specific and not yet shared by admission, scheduling, or non-sandbox runtime paths
6. effect-journal and checkpoint authority are not yet consumed by live workload execution

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
