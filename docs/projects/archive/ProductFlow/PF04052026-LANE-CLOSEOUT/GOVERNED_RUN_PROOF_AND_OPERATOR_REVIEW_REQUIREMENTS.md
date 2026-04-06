# Governed Run Proof And Operator Review Requirements
Last updated: 2026-04-05
Status: Accepted archived requirements companion
Owner: Orket Core
Implementation plan: `docs/projects/archive/ProductFlow/PF04052026-LANE-CLOSEOUT/PRODUCTFLOW_IMPLEMENTATION_PLAN.md`

## Purpose

Define the next high-value Orket requirements bundle that combines:

1. promotion of one end-to-end governed runtime path from staged to undeniable,
2. extension of the truthful-runtime story beyond packet-1 into operator-legible packet-2 surfaces, and
3. elevation of evidence and replay into a first-class operator review experience.

The goal of this bundle is not to add more architecture in the abstract.
The goal is to make one governed Orket run feel undeniably real, truthful, inspectable, and reviewable.

## Scope

In scope:

1. one canonical governed run path,
2. packet-2 truthful-runtime surfaces for that path,
3. operator review artifacts and replay surfaces,
4. proof gates for live execution, review, and replay,
5. boundary rules that keep review convenience subordinate to runtime truth.

Out of scope:

1. broad ControlPlane lane reopening,
2. generic UI design,
3. adding a second result-class regime,
4. Prompt Reforger as a primary lane,
5. provider-breadth expansion except where required to execute the canonical governed run.

## Authority and precedence

This document is subordinate to current repo truth and does not replace existing accepted authority.

Precedence for overlapping topics is:

1. `CURRENT_AUTHORITY.md` for present-tense shipped behavior,
2. `docs/ROADMAP.md` for lane posture,
3. `docs/ARCHITECTURE.md` for canonical result vocabulary,
4. `docs/projects/ControlPlane/orket_control_plane_packet/00A_CONTROL_PLANE_GLOSSARY_AND_ENUM_AUTHORITY.md` for `FinalTruthRecord` and shared control-plane enums,
5. `docs/specs/TRUTHFUL_RUNTIME_PACKET1_CONTRACT.md` for boundary-scoped packet-1 truth classification, classification precedence, and packet-1 defect triggers,
6. `docs/specs/CORE_RUNTIME_STABILITY_REQUIREMENTS.md` for emitted-versus-derivable runtime truth, including derivable terminal-summary truth,
7. `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md` for `replay_ready` and `stability_status` surfaces,
8. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` for claim tiers, compare scope, operator surface, policy digest, and control-bundle linkage,
9. this document for the new bundle-specific requirements.

If a requirement here conflicts with already accepted runtime truth, the implementation plan must resolve the conflict explicitly rather than silently introducing a second story.

## Core assertion

Orket must be able to execute one bounded governed run and leave behind enough truthful machine-readable evidence that an operator can answer all of the following without narrative glue:

1. what was intended,
2. what actually happened,
3. which actions were proposed, approved, denied, skipped, emitted, or left pending,
4. which outputs or effects carried packet-1 repair, degradation, mismatch, or defect facts,
5. why the run finished with its terminal `FinalTruthRecord.result_class`,
6. separately, which boundary-scoped packet-1 truth classifications applied to qualifying outputs or effects,
7. whether the observed outcome is `replay_ready` and, when compared, whether `stability_status` is `stable`, `diverged`, `not_evaluable`, or `blocked`.

## Definitions

### D-01. Canonical governed run

The canonical governed run is the single bounded workflow selected for this lane to prove the product surface.
It must be real, live, and operator-meaningful.
It must not be a synthetic no-op chosen only because it is easy to make green.

### D-02. Golden path

The golden path is the exact start-to-terminal path for the canonical governed run, including any approval pause, continuation decision, emitted artifacts, and review outputs.

### D-03. Packet-1

Packet-1 remains the minimal truthful-runtime surface for provenance, classification, mismatch, fallback, and defect facts already frozen elsewhere.

### D-04. Packet-2

Packet-2 is the next operator-legible truth layer.
It explains the run in machine-readable review form without changing packet-1 authority.
It may derive, organize, and expose truth already recorded by the runtime, but it may not rewrite or soften that truth.

### D-05. Operator review package

The operator review package is the bounded artifact family produced for the canonical governed run so an operator can inspect, reason about, and replay-review the run without reading raw code or reconstructing the story manually.

## Bundle objective

This bundle is complete only when one canonical governed run can be:

1. executed live,
2. paused or reviewed at at least one governed decision seam,
3. truthfully finalized,
4. inspected through packet-1 and packet-2 surfaces,
5. reviewed through a first-class operator review package, and
6. replay-reviewed or truthfully reported as not `replay_ready` or compare-blocked under existing replay policy.

`stability_status=not_evaluable` is admissible review-surface truth when comparative evidence does not yet exist, but it is not sufficient by itself to satisfy the bundle-complete replay-review obligation.

The bundle is not complete when the repo can do these things in pieces but no single run proves them together.

## Section 1: Canonical governed-run requirements

### GR-01. One canonical governed run only

The lane must select exactly one canonical governed run.
Additional examples may exist, but they are subordinate.
The lane must not require operators to infer the product surface from several half-overlapping demos.

### GR-02. Real runtime path, not demo-only scaffolding

The canonical governed run must execute through shipped runtime seams.
It must not use a special-case demo runner that bypasses normal session, approval, artifact, or closure behavior.
Any demo helper must be a thin wrapper over the canonical runtime path.

### GR-03. Bounded but meaningful workflow

The canonical governed run must be narrow enough to execute repeatedly, but rich enough to prove Orket's value.
At minimum, the run must include:

1. one bounded intent or workload request,
2. one governed decision or approval seam,
3. one application-owned side-effect proposal or effect boundary,
4. one terminal closure outcome, and
5. one emitted artifact family sufficient for review.

### GR-04. Host-owned truth remains visible

The canonical governed run must preserve the current Orket boundary that applications own side effects.
If the runtime proposes an effect and the host or application boundary owns emission, the recorded artifacts must make that split explicit.
The runtime must not pretend it directly performed an application-owned side effect when it only proposed or staged it.

### GR-05. Governed interruption is part of the path

If the canonical run requires operator approval, operator absence, or bounded policy gating, that seam must remain visible in the golden path.
The lane must not hide the governed seam just to make the demo look smoother.
This requirement concerns run-path visibility, not boundary-scoped packet-1 truth assignment.

### GR-06. Failure is admissible and must remain truthful

The canonical governed run may terminate with any existing `FinalTruthRecord.result_class` allowed by current authority:

1. `success`
2. `failed`
3. `blocked`
4. `degraded`
5. `advisory`

Packet-1 truth classification and replay/stability status are separate surfaces and must not be fused into a new mixed outcome label.
The lane is still valid if the chosen run ends in a non-ideal but truthful state.
The lane is invalid if it manufactures a smoother terminal outcome by suppressing blockers, fallbacks, repair facts, or packet-1 defects.

### GR-07. Canonical entrypoints are frozen

The lane must freeze one canonical operator entrypoint for:

1. live execution,
2. review-package generation when distinct from live execution,
3. replay or replay-compare review.

Wrapper aliases may exist, but one canonical path must be documented and used in proofs.

### GR-08. Walkthrough contract exists

The repo must contain one bounded operator walkthrough for the canonical governed run.
That walkthrough must name:

1. prerequisites,
2. the canonical commands,
3. expected pause or approval seams,
4. expected artifact outputs,
5. the review sequence after run completion.

## Section 2: Packet-2 truthful-runtime requirements

### P2-01. Packet-2 is subordinate to packet-1

Packet-2 may reorganize, summarize, and cross-link truth already recorded by the runtime.
Packet-2 may add operator-legible derived fields.
Packet-2 may not contradict packet-1, replace packet-1, or introduce a second classification authority.

### P2-02. Machine-readable before narrative

Packet-2 must be machine-readable first.
Human-readable summaries may exist, but the canonical packet-2 surface must be structured and inspectable without prose interpretation.

### P2-03. Intent versus observation split

Packet-2 must distinguish at minimum:

1. intended action,
2. proposed action,
3. approved action,
4. observed execution or emitted effect,
5. derived conclusion,
6. attested human input when present.

These classes must not collapse into a single "done" field.

### P2-04. Repair and degradation chain visibility

If the run relied on repair, retry, fallback, degradation, or bounded operator acceptance, packet-2 must record:

1. what triggered the divergence,
2. what recovery path was taken,
3. whether the recovery was explicit or silent,
4. how the final truth classification was affected.

### P2-05. Selected boundary and closure basis

Packet-2 must make visible which boundary output, effect record, or terminal condition was selected as the basis for closure.
If no qualifying output exists, packet-2 must say so explicitly instead of manufacturing one.

### P2-06. Source attribution classes are explicit

Packet-2 must preserve explicit attribution classes for review-relevant facts.
At minimum, the implementation must distinguish among:

1. observed,
2. derived,
3. attested,
4. projected,
5. repaired,
6. blocked or unavailable.

Equivalent names may be used only if one stable enum family is frozen before implementation completion.

### P2-07. Effect lineage is inspectable

For every operator-significant proposed or emitted effect in the canonical governed run, packet-2 must make it possible to inspect:

1. which step proposed it,
2. which policy or approval seam constrained it,
3. whether it was approved, denied, skipped, emitted, or left pending,
4. which durable record proves that state.

### P2-08. Packet-2 reconstruction is ledger-subordinate

When packet-2 fields are reconstructible from existing runtime evidence, the canonical reconstruction path must derive them from durable runtime truth rather than from ad hoc rereads of mutable workspace bytes.
If some packet-2 field cannot currently be reconstructed from durable truth, that limitation must be recorded explicitly.

### P2-09. Packet-2 does not rewrite final truth

Packet-2 may clarify why a run is degraded, repaired, or blocked.
It may describe boundary-scoped packet-1 repair, degradation, mismatch, or defect facts attached to qualifying outputs or effects.
It may not invent a run-level packet-1 classification, reclassify a degraded run as direct, erase residual uncertainty, or upgrade insufficient evidence into sufficient evidence.

## Section 3: Operator review package requirements

### RV-01. One bounded review package per canonical run

The canonical governed run must produce one bounded operator review package.
The review package must be discoverable from a single stable root or index artifact.

### RV-02. Review index artifact

The review package must expose a machine-readable review index that points to the authoritative artifacts needed for inspection.
At minimum, that index must reference:

1. run identity,
2. terminal `FinalTruthRecord`,
3. packet-1 surfaces,
4. packet-2 surfaces,
5. approval or operator-action receipts when present,
6. effect records,
7. terminal summary projection when present,
8. replay inputs, replay compare artifacts, or replay-blocker record.

### RV-03. Review package is evidence-first

The review package must organize evidence.
It must not become a second runtime.
If a convenience summary disagrees with an authoritative artifact, the authoritative artifact wins and the inconsistency must be treated as a defect.

### RV-04. Review sequence is frozen

The repo must define one canonical review sequence for the canonical governed run.
That sequence must let an operator answer, in order:

1. what run this is,
2. what was requested,
3. what path the runtime took,
4. what actions or effects were governed,
5. what terminal run-closure truth was assigned through `FinalTruthRecord`,
6. which boundary-scoped packet-1 truth classifications applied to qualifying outputs or effects,
7. whether the run is `replay_ready` and, when compared, whether `stability_status` is `stable`, `diverged`, `not_evaluable`, or `blocked`.

### RV-05. Replay-readiness is explicit

The review package must explicitly expose replay-readiness and stability status using existing authority surfaces rather than a new review-only enum family.
At minimum, the package must expose:

1. whether the canonical run is `replay_ready`, and
2. when comparative evidence exists or compare is attempted, `stability_status=stable|diverged|not_evaluable|blocked`.

If replay is not ready or compare is blocked, the package must record the blocker class rather than leaving replay status implicit.

### RV-06. Compare outputs are operator-meaningful

When replay or compare is executed for the canonical run, the resulting comparison surface must be intelligible to an operator.
It must distinguish at minimum:

1. in-scope match supporting `stability_status=stable`,
2. in-scope divergence supporting `stability_status=diverged`,
3. blocked compare supporting `stability_status=blocked`,
4. `not_evaluable` when comparative evidence does not yet exist.

`not_evaluable` is truthful review-package status, but it does not satisfy bundle completion unless some other requirement in this document expressly allows completion at a blocked boundary instead.

### RV-07. Review package supports absence truth

The review package must be able to show absence truth explicitly.
Examples include:

1. no operator approval occurred,
2. no emitted side effect occurred,
3. no qualifying boundary output existed,
4. no replay proof was possible.

Absence must remain visible as absence, not be replaced with an implied positive state.

### RV-08. Review surface is code-independent

An operator must be able to complete the canonical review flow using the review package, documented commands, and emitted artifacts without reading implementation code.
This does not require a GUI.
It does require that the artifact and command surfaces are coherent enough to stand on their own.

## Section 4: Proof and gate requirements

### PG-01. Live proof is mandatory

The bundle must include at least one live proof execution of the canonical governed run.
Structural-only proof is insufficient for lane completion.

### PG-02. Truthful blocked proof is admissible

If some secondary proof surface cannot run live, the bundle may still complete only when the blocked surface records:

1. the exact attempted step,
2. the exact blocker,
3. the last proven layer.

The lane may not claim full proof completion past that boundary.

### PG-03. Replay proof is tied to the same canonical run

Replay or replay-compare proof for this lane must use the same canonical governed run that proves the live path.
The lane may not satisfy live proof with one run and replay proof with a different easier run unless that split is explicitly accepted in this requirements doc.
This requirements doc does not accept that split.
Any replay claim emitted for this lane must carry first-class same-run claim surfaces required by `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`, including `claim_tier`, `compare_scope`, `operator_surface`, `policy_digest`, and `control_bundle_ref` or `control_bundle_hash`.
Explicit mapping is admissible only when the lane is reusing a pre-existing legacy proof artifact family whose shape predates this lane.
This legacy-mapping exception may not be used to justify omission of first-class claim fields from any new proof artifact family introduced by this lane.

### PG-04. Operator review proof exists

The bundle must prove not only that artifacts were emitted, but that the canonical review sequence can actually be completed from them.
At minimum, one proof artifact or report must confirm that the required review questions were answerable from the emitted package.

### PG-05. Proof claim surfaces are explicit

Every new proof artifact family emitted for this lane must truthfully label with first-class fields:

1. `proof_mode`,
2. `proof_result`,
3. canonical run id or equivalent identity,
4. `claim_tier`,
5. `compare_scope`,
6. `operator_surface`,
7. `policy_digest`,
8. `control_bundle_ref` or `control_bundle_hash`,
9. model/provider/prompt selection metadata,
10. evidence artifact path or canonical evidence reference,
11. `replay_ready` and `stability_status` when applicable.

If the lane reuses a pre-existing legacy proof artifact family, an explicit mapping document may bridge missing claim fields only as temporary compatibility debt.
That bridge must identify the legacy family, enumerate each mapped field, and may not be cited as compliance for any new artifact family created by this lane.

### PG-06. No green-by-exclusion review proof

The lane must not pass review proof by excluding the exact artifacts that contain the difficult truth.
If a surface is operator-significant for the canonical run, it must remain in-scope for review.

## Section 5: Boundary and anti-drift requirements

### AD-01. No new result regime

This lane must not introduce a second run-result, packet-1 truth-classification, or replay/stability vocabulary for the same run.
`FinalTruthRecord.result_class`, packet-1 truth classification, and replay/stability status must remain separate authorities.
Any additional review labels must be explicitly subordinate to one of those existing surfaces.

### AD-02. No silent duplication of authority

If packet-2, review-package, replay, and run-summary surfaces all expose related conclusions, the implementation must define which one is authoritative for each field family.
The lane must not rely on "they should probably match" as the authority rule.

### AD-03. No special-case product story

The canonical governed run must represent the product story Orket intends to tell.
The lane must not create a one-off showcase that the normal runtime path cannot reproduce.

### AD-04. Narrow reopen only

This bundle may require targeted fixes in session, approval, artifact, replay, or control-plane seams.
It does not authorize broad architectural reopen of paused lanes unless a concrete blocker proves that narrower repair is impossible.

### AD-05. Stable names before completion

Before lane closeout, the implementation must freeze the canonical names and paths for the review package artifacts and commands.
Closeout is not complete while those surfaces are still described with placeholder names.

## Acceptance criteria

This requirements draft is acceptable for implementation planning only when all of the following are true:

1. it names one canonical governed run instead of several partial demos,
2. it keeps packet-2 subordinate to existing runtime truth rather than inventing a second truth layer,
3. it requires a first-class operator review package rather than assuming operators will manually inspect raw logs,
4. it ties live proof, review proof, and replay proof to the same canonical run,
5. it allows truthful blocked outcomes without rewarding concealed blockers,
6. it preserves application-owned side-effect boundaries and does not let the runtime overclaim execution authority,
7. it is specific enough that an implementation plan can name concrete commands, artifacts, and proof gates without reopening the objective.

## Suggested implementation-plan obligations

The implementation plan that follows this requirements doc should, at minimum:

1. select the canonical governed run,
2. freeze the canonical live, review, and replay commands,
3. freeze packet-2 artifact names and review-index names,
4. name the concrete runtime seams to touch,
5. define live-proof, review-proof, and replay-proof exit gates,
6. identify any blocker that requires a narrow reopen of a paused lane.
