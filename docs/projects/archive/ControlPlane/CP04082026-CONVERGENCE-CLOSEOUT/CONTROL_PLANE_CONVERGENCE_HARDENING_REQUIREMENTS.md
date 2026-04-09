# Control-Plane Convergence Hardening Requirements
Last updated: 2026-04-08
Status: Completed archived requirements companion
Owner: Orket Core
Lane type: Control-plane convergence / hardening

Paired implementation authority:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`

Closeout authority:
1. `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CLOSEOUT.md`

## Authority posture

This document is the archived scoped requirements companion for the completed ControlPlane convergence lane formerly recorded in `docs/ROADMAP.md`.
It is not the implementation authority.

The active ControlPlane requirements authority remains the accepted packet under `docs/projects/ControlPlane/orket_control_plane_packet/`.
The paired archived implementation authority is `docs/projects/archive/ControlPlane/CP04082026-CONVERGENCE-CLOSEOUT/CONTROL_PLANE_CONVERGENCE_IMPLEMENTATION_PLAN.md`.
The earlier packet-v2 implementation sequencing lane remains archived under `docs/projects/archive/ControlPlane/CP03262026-LANE-CLOSEOUT/`.

## Purpose

Finish the accepted control-plane foundation by eliminating mixed-regime runtime behavior.

This lane exists to converge the runtime from:
1. packet-v2 authority surfaces implemented on selected paths
2. partial first-class object coverage
3. subsystem-specific truth publication
4. ambient or reconstructed control-plane behavior

into:
1. one default control-plane write path
2. one coherent first-class object model across all governed execution paths
3. one authoritative closure model
4. one bounded operator / recovery / reconciliation model
5. one namespace- and effect-aware execution discipline

This lane is not a new vocabulary packet.
It is a convergence and universalization lane.

## Authority dependencies

This lane depends on:
1. `00_CONTROL_PLANE_FOUNDATION_PACKET.md`
2. `00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md`
3. `00B_CURRENT_STATE_CROSSWALK.md`
4. `01` through `12` of the accepted packet
5. the accepted architecture direction in `09_OS_MASTER_PLAN.md`

This lane must not redefine packet nouns or shared enums.

## Problem statement

The current runtime has meaningful control-plane adoption, but it remains hybrid.

Known remaining risks include:
1. reservation truth not wired into all admission and scheduling paths
2. lease truth not shared by admission, scheduling, or most non-sandbox runtime paths
3. operator-action authority still fragmented outside selected authenticated and approval-driven paths
4. effect truth still often reconstructed from artifacts instead of being published through the normative effect journal
5. checkpoint publication and supervisor-owned checkpoint acceptance still not execution-default
6. namespace and safe-tooling gates still not shared by broader runtime workloads, scheduling, and resource targeting
7. workload identity still conflicting across runtime workloads, rocks, and extension entrypoints
8. run truth, effect truth, reconciliation truth, and final-truth closure still partly split across older surfaces

## Design stance

This lane must optimize for:
1. convergence over new breadth
2. default-path authority over selective-path authority
3. replacement of ambient truth with published truth
4. promotion of still-partial nouns into first-class runtime objects
5. proof that old and new paths cannot silently disagree

## Cross-lane invariants

### CH-01. No second vocabulary
No implementation slice may introduce a second control-plane vocabulary outside the accepted glossary authority.

### CH-02. No reconstructed authority when published authority is required
If a requirement family says a truth surface must be published through a first-class record or journal, the runtime must not satisfy that surface by reconstructing truth from scattered artifacts after the fact.

### CH-03. No ambient escalation
Capability, namespace, reservation, lease, recovery, reconciliation, and operator semantics must fail closed when declarations or required records are missing.

### CH-04. No split-brain closure
A governed run must close through one authoritative final-truth path.
Legacy closure artifacts may remain as projections or compatibility views, but they must not act as alternate closure authorities.

### CH-05. No resume by implication
Checkpoint existence, snapshot existence, or saved state existence must never imply resumability without explicit supervisor acceptance and a recovery decision.

## Requirements

## Section A - Universal workload, run, and attempt authority

### CC-01. Canonical workload identity
The runtime must expose one canonical governed workload definition surface used by:
1. runtime workloads
2. rocks
3. extension entrypoints
4. workload composition and child workload rules
5. safe tooling attribution

Parallel workload nouns may remain temporarily only as compatibility adapters and must map explicitly to the canonical workload object.

### CC-02. Canonical run authority
The runtime must expose one authoritative run object whose identity survives:
1. recovery
2. replay
3. reconciliation
4. closeout
5. operator interaction

Run identity must stop being split between review flow objects and observability artifacts.

### CC-03. First-class attempt history
The runtime must expose a durable append-only attempt object family.

Attempt history must:
1. survive retries
2. distinguish resumed execution from new-attempt execution
3. support reconciliation and final-truth closure
4. prevent loop-shaped retry logic from erasing history

### CC-04. Step and effect attribution
Every governed effectful or closure-relevant action must be attributable at minimum to:
1. workload
2. run
3. attempt
4. step
5. authorization basis

## Section B - Reservation, lease, and resource convergence

### CC-05. Reservation as default admission truth
Any path that performs admission, concurrency gating, exclusivity checks, claim publication, or resource scheduling must publish first-class reservation truth when reservation semantics are involved.

No admission or scheduling path may publish undefined or implied reservation nouns.

### CC-06. Lease as default active ownership truth
Any path that begins active ownership, active mutation, or exclusive resource control must publish first-class lease truth.

Lease truth must not remain sandbox-only or subsystem-specific.

### CC-07. Reservation-to-lease discipline
Promotion from reservation to lease must be:
1. explicit
2. durable
3. supervisor-authorized
4. attributable to the governing run and attempt
5. reversible or reconcilable on failure where policy allows

### CC-08. Resource registry convergence
Resource truth must converge into one general resource model.
Sandbox resources may remain one concrete instance of that model, but must not remain a special-case authority family.

## Section C - Effect journal and checkpoint universalization

### CC-09. Effect journal as default write path
Any mutating or closure-relevant governed path must publish effect truth through the normative effect journal.

Artifact reconstruction may support debugging or compatibility, but must not remain the authoritative effect path.

### CC-10. Journal integrity and ordering
The runtime must guarantee ordered, append-only, integrity-verifiable effect publication for all governed effect paths.

### CC-11. Checkpoint publication as explicit supervisor surface
Checkpoint publication must be a supervisor-owned control-plane act, not an accidental byproduct of saving state.

### CC-12. Resume only by accepted checkpoint and recovery decision
A resume path is legal only when:
1. a checkpoint exists,
2. the checkpoint remains admissible,
3. the supervisor accepts resumability,
4. a recovery decision authorizes resume mode explicitly.

### CC-13. Default checkpoint policy
The runtime must define which governed execution boundaries are:
1. checkpoint-required,
2. checkpoint-eligible,
3. checkpoint-forbidden.

Checkpoint creation must become execution-default where recovery safety or replayability depends on it.

## Section D - Recovery, reconciliation, operator, and closure convergence

### CC-14. Recovery decision universalization
Recovery authority must move from service-local logic into durable first-class recovery-decision records across all governed recovery paths.

### CC-15. Reconciliation universalization
Subsystem-specific reconciliation must be promoted into one authoritative reconciliation record family with stable divergence classes and safe continuation classes.

### CC-16. Operator action universalization
Any operator command, operator risk acceptance, or operator attestation affecting governed execution must publish one first-class operator-action record family.

Operator influence must stop being scattered across endpoint behavior, logs, and ad hoc policies.

### CC-17. Final-truth record as sole closure authority
Every governed terminal run must publish one first-class `FinalTruthRecord`.

Legacy run-summary or packet-1 style surfaces may remain as derived read models, but not as alternate closure authorities.

### CC-18. Closure truth inputs
A `FinalTruthRecord` must derive its authority from published control-plane records, including where applicable:
1. lifecycle truth
2. attempt history
3. effect journal truth
4. reconciliation records
5. recovery decisions
6. operator actions
7. checkpoint acceptance records

### CC-19. Operator boundaries remain hard
Operator risk acceptance is never evidence of world state.
Operator attestation is policy-bounded and remains visibly distinct from observation.
Operator commands may change terminality or continuation but may not rewrite truth classification.

## Section E - Namespace and tooling convergence

### CC-20. Namespace as default boundary
Any governed resource targeting, child workload composition, or tool scope targeting must consume one explicit namespace authority surface.

Ambient namespace or implicit shared-resource visibility is prohibited.

### CC-21. Safe-tooling default path
Any governed tool invocation must consume the accepted safe-tooling contract family and must not bypass:
1. capability declarations
2. namespace rules
3. reservation and lease truth
4. effect-journal publication
5. operator-gate rules
6. degraded-mode restrictions

### CC-22. No non-governed mutation path
Any runtime path that can mutate governed state must either:
1. integrate fully with the control plane, or
2. be explicitly marked out of governed execution and blocked from governed closure claims.

## Section F - Documentation and authority-story convergence

### CC-23. One authority story in docs
The packet, roadmap, indexes, README surfaces, and archived lane material must tell one consistent authority story about:
1. what is active implementation authority,
2. what is archived historical sequencing,
3. what remains open,
4. which lane owns convergence work.

### CC-24. Crosswalk remains live
The current-state crosswalk must be updated as each remaining gap is converged.
A slice is incomplete if the crosswalk still claims the old fragmented surface without an explicit migration note.
Each implementation slice must update the touched crosswalk row or rows in the same change as the code and proof it promotes.

### CC-25. Compatibility exits are explicit
Any temporary adapter, projection, or legacy truth surface kept during convergence must have:
1. a named owning workstream,
2. a removal or projection-only condition,
3. an explicit note that it is not active authority while the new surface is in force.

## Acceptance criteria

This lane is acceptable only when:
1. workload, run, attempt, effect, operator action, recovery decision, reconciliation record, and final truth are all first-class on the governed paths they claim to cover
2. effect truth is no longer authoritatively reconstructed from scattered artifacts on governed mutation paths
3. checkpoint existence cannot be mistaken for checkpoint authority
4. reservation and lease truth are default-path behavior across governed admission and ownership paths
5. namespace and safe-tooling gates are the default boundary rather than selective add-ons
6. terminal closure is authored through one `FinalTruthRecord` family
7. every temporary compatibility surface still kept for migration has a named owner, a removal or projection-only gate, and a non-authority note
8. docs, crosswalk, code, and proofs tell one consistent story

## Proof requirements

Structural proof:
1. no alternate enum families
2. no alternate closure authority path
3. no reservation-free governed ownership path
4. no resume-by-snapshot-existence path
5. no operator-input collapse between command, risk acceptance, and attestation
6. no tool mutation path without effect-journal linkage
7. no temporary compatibility surface lacks an owner and exit condition

Integration proof:
1. representative admission and scheduling paths publish reservation truth
2. representative mutation paths publish lease and effect-journal truth
3. representative recovery paths publish checkpoint acceptance and recovery decisions
4. representative operator paths publish first-class operator-action truth
5. representative closeout paths publish one `FinalTruthRecord`

Live proof where real surfaces are involved:
1. effect-boundary uncertainty forces reconcile-or-stop
2. false completion claim is rejected from final truth
3. stale or orphan lease cannot silently continue
4. degraded operator-approved continuation remains visibly degraded
5. namespace drift and undeclared capability escalation fail closed
