# DG03192026 Governed Evidence Hardening Plan

Last updated: 2026-03-20
Status: Archived
Owner: Orket Core
Lane type: Archived techdebt cycle

Archive note:
1. Completed and archived on 2026-03-20.
2. Closeout authority: [docs/projects/archive/techdebt/DG03192026/Closeout.md](docs/projects/archive/techdebt/DG03192026/Closeout.md)

## Purpose

Turn the determinism, provenance, and extension-seam hardening direction into one bounded implementation lane.

This cycle exists to reduce authority drift between:
1. the new determinism gate policy,
2. runtime provenance and artifact surfaces,
3. tool determinism and failure contracts,
4. bounded deterministic detectors,
5. the SDK/extension migration seam.

The cycle is intentionally narrow:
1. fewer truth surfaces,
2. stronger provenance,
3. more first-class failure truth,
4. less dependence on prompt luck or model-specific narratives.

Implementation must not begin until the Decision Lock section below is present and frozen in the active plan.

## Source Inputs

1. `AGENTS.md`
2. `CURRENT_AUTHORITY.md`
3. `docs/CONTRIBUTOR.md`
4. `docs/ROADMAP.md`
5. [docs/specs/ORKET_DETERMINISM_GATE_POLICY.md](docs/specs/ORKET_DETERMINISM_GATE_POLICY.md)
6. [docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md](docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md)
7. [docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md](docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md)
8. [docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md](docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md)
9. [docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md](docs/specs/CORE_TOOL_RINGS_COMPATIBILITY_REQUIREMENTS.md)
10. [docs/specs/RUNTIME_INVARIANTS.md](docs/specs/RUNTIME_INVARIANTS.md)
11. [docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md](docs/specs/PROTOCOL_GOVERNED_LOCAL_PROMPTING_CONTRACT.md)
12. [docs/guides/external-extension-authoring.md](docs/guides/external-extension-authoring.md)
13. current extension workload provenance surfaces in `orket/extensions/`
14. current standalone workload probes in `scripts/workloads/`

## Current Truth

1. [docs/specs/ORKET_DETERMINISM_GATE_POLICY.md](docs/specs/ORKET_DETERMINISM_GATE_POLICY.md) now defines claim tiers, compare scope, operator surface, and gate semantics, but many artifact families still satisfy it only through transition-rule mapping rather than first-class fields.
2. Provenance, `plan_hash`, `policy_digest`, and artifact manifest surfaces already exist in parts of the repo, especially the extension workload path, but they are not yet unavoidable across the serious artifact families that make determinism or auditability claims.
3. Tool determinism class and `determinism_violation` are already active concepts in the runtime and specs, but they are not yet promoted consistently into operator-facing proof and release truth.
4. The canonical runtime event artifact path remains `agent_output/observability/runtime_events.jsonl`.
   1. This lane preserves that path rather than creating a second per-session or per-turn `runtime_events.jsonl` regime.
   2. Any earlier draft references to `observability/<session_id>/<issue_id>/<turn_dir>/runtime_events.jsonl` are narrowed out in favor of the existing canonical surface.
5. The bounded S-04 code-review probe showed the right truth split:
   1. deterministic detection stayed stable on the fixture,
   2. weaker model or prompting paths regressed,
   3. model output remained useful for explanation and fixes, but not as the only truth surface.
6. The SDK/extension seam is real and already has:
   1. a guide,
   2. validation flow,
   3. templates,
   4. runtime provenance.
7. What is still missing is a shippable migration pack rather than a loose collection of extension-facing pieces.

## Implementation Status

Landed in this lane so far:
1. The locked runtime provenance family now carries first-class governed identity on the extension workload path:
   1. `provenance.json`
   2. `artifact_manifest.json`
   3. `ExtensionRunResult`
2. The locked proof/publication consumer now supports governed claim fields, and one real governed staging row exists:
   1. `STAGE-GEN-008` in [benchmarks/staging/index.json](benchmarks/staging/index.json)
   2. governed bundle at [benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json](benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json)
3. The locked failure-truth path now carries structured `determinism_violation` data through the preserved canonical runtime event stream at `agent_output/observability/runtime_events.jsonl`.
4. The bounded `S-04` probe now carries first-class claim surfaces and an explicit split between:
   1. authoritative deterministic truth
   2. supplementary model-assisted review
5. Migration work for this lane remains boundary/scaffolding only and has been documented rather than expanded into a second lane.

Evidence anchors for the current implementation state:
1. [benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json](benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json)
2. [benchmarks/staging/General/dg03192026_extension_run_result_identity_2026-03-19.json](benchmarks/staging/General/dg03192026_extension_run_result_identity_2026-03-19.json)
3. [benchmarks/staging/General/dg03192026_extension_provenance_extract_2026-03-19.json](benchmarks/staging/General/dg03192026_extension_provenance_extract_2026-03-19.json)
4. [benchmarks/staging/General/dg03192026_extension_artifact_manifest_extract_2026-03-19.json](benchmarks/staging/General/dg03192026_extension_artifact_manifest_extract_2026-03-19.json)
5. [benchmarks/staging/General/dg03192026_s04_proof_summary_2026-03-19.json](benchmarks/staging/General/dg03192026_s04_proof_summary_2026-03-19.json)
6. [benchmarks/staging/General/dg03192026_s04_deterministic_decision_2026-03-19.json](benchmarks/staging/General/dg03192026_s04_deterministic_decision_2026-03-19.json)

## Scope

In scope:
1. one runtime provenance family:
   1. `provenance.json`
   2. `artifact_manifest.json`
   3. `ExtensionRunResult`
2. one proof/publication consumer:
   1. `benchmarks/staging/index.json`
3. one failure-truth path:
   1. `determinism_violation` emitted to `agent_output/observability/runtime_events.jsonl`
4. one bounded detector scope:
   1. `S-04` only
5. migration-pack boundary and scaffolding only:
   1. migration-pack boundary defined
   2. reference extension target chosen
   3. conformance entrypoint chosen
   4. deprecation table skeleton added
6. update roadmap/docs/spec references as needed to keep authority aligned

Out of scope:
1. broad runtime architecture rewrite
2. general-purpose deterministic code review beyond bounded declared classes
3. retrofitting every historical artifact family in one cycle
4. large prompt-optimization or model-selection campaigns as the center of the lane
5. treating lab leaderboard wins as product truth
6. no parallel proof/result schema regime when existing artifact families can be extended in place

## Success Criteria

1. The first-pass runtime provenance family `provenance.json` + `artifact_manifest.json` + `ExtensionRunResult` exposes first-class determinism-policy and governed identity linkage rather than transition-rule-only mappings.
2. The first-pass proof/publication consumer `benchmarks/staging/index.json` carries or explicitly maps the locked claim surfaces for the in-scope runtime family without introducing a second result regime.
3. The locked runtime family carries one unbroken governed chain from inputs/materials to plan or input identity, policy/config identity, produced artifact identity, and provenance identity.
4. Missing provenance or broken linkage fails closed on the in-scope governed path.
5. Determinism class and `determinism_violation` become visible on the locked runtime/proof path rather than remaining only implicit in lower-level runtime internals.
6. `S-04` is the only bounded detector scope admitted to this lane, and its deterministic must-catch classes remain the primary truth surface for release/publication claims on that scope.
7. Migration-pack boundary defined, reference extension target chosen, conformance entrypoint chosen, and deprecation/removal table skeleton added.
8. `python scripts/governance/check_docs_project_hygiene.py` passes.

## Current Assessment Against Success Criteria

1. satisfied:
   the locked runtime provenance family now exposes first-class governed identity linkage on the extension workload path
2. satisfied:
   the locked proof/publication consumer now carries one explicit governed staging row without introducing a second result regime
3. satisfied:
   the locked runtime family now carries the governed chain from input identity through manifest and provenance linkage
4. satisfied:
   the locked governed runtime path fails closed when required linkage or artifact integrity breaks
5. satisfied:
   determinism class and `determinism_violation` are visible on the locked runtime/proof path
6. partially satisfied but truthfully bounded:
   `S-04` deterministic must-catch truth is primary on the declared fixture scope, but the staged/publication-facing claim remains `non_deterministic_lab_only`
7. satisfied:
   migration boundary/scaffolding items for this lane exist and full pack work remains explicitly deferred
8. satisfied:
   docs hygiene remains green

## Locked First-Pass Scope

This lane upgrades one runtime provenance family and one proof/publication consumer only.

Locked runtime provenance family:
1. extension workload provenance bundle only:
   1. `provenance.json`
   2. `artifact_manifest.json`
   3. `ExtensionRunResult`

Locked proof/publication consumer:
1. `benchmarks/staging/index.json`

Locked failure-truth path:
1. `determinism_violation` emitted to `agent_output/observability/runtime_events.jsonl`
2. this preserves the existing canonical runtime event artifact stream instead of introducing a second observability regime for this lane

Locked bounded detector scope:
1. `S-04` only

Locked migration status:
1. full migration-pack implementation is deferred from this first slice
2. only these boundary/scaffolding items are in scope:
   1. migration-pack boundary defined
   2. reference extension target chosen
   3. conformance entrypoint chosen
   4. deprecation/removal table skeleton added

Excluded from the locked first pass:
1. standalone workload probe artifact families beyond `S-04`
2. additional bounded detector classes
3. full migration-pack implementation
4. any new proof/result schema regime when an existing family can be extended in place

## Decision Lock

Objective:
1. freeze the first implementation slice before code begins so the lane does not dissolve into schema churn or opportunistic scope growth

Lock:
1. first runtime artifact family:
   1. `provenance.json`
   2. `artifact_manifest.json`
   3. `ExtensionRunResult`
2. first proof/publication consumer:
   1. `benchmarks/staging/index.json`
3. first failure-truth path:
   1. `determinism_violation` emitted to `agent_output/observability/runtime_events.jsonl`
4. first bounded detector scope:
   1. `S-04` only
5. migration work status:
   1. deferred except for boundary/scaffolding items listed in the Locked First-Pass Scope
6. required governed identity chain for the locked runtime and proof surfaces:
   1. `claim_tier`
   2. `compare_scope`
   3. `operator_surface`
   4. `policy_digest`
   5. `control_bundle_ref` or `control_bundle_hash`
   6. `plan_hash` or equivalent stable input identity
   7. artifact manifest hash or reference
   8. provenance reference or hash
7. mapping-only compliance remains temporary only where the active determinism gate policy explicitly allows it; the locked runtime family and locked proof consumer are the first upgrade targets away from transition-rule-only compliance

Acceptance:
1. no implementation starts before this lock is written into the active plan
2. the cycle has one bounded runtime family and one bounded proof/publication consumer
3. the governed identity chain is the same across the locked runtime and proof surfaces
4. no second provenance regime or second proof/result regime is introduced
5. changes after lock require explicit lane amendment, not silent iteration

Proof target:
1. structural

## Workstream 1: Make Extension Workload Provenance And Identity Unavoidable

Status:
1. substantially landed on the locked runtime family

Objective:
1. make governed execution provenance the currency of serious proof, not merely successful output

Actions:
1. upgrade `provenance.json`, `artifact_manifest.json`, and `ExtensionRunResult` to carry or reference the locked governed identity chain
2. fail closed when required linkage is missing or contradictory
3. ensure reruns can explain why they differ through digest or identity mismatch rather than manual interpretation
4. preserve one canonical provenance path from materials or inputs to produced artifacts

Acceptance:
1. the locked runtime family cannot claim governed proof without complete linkage
2. provenance drift is visible as machine-readable mismatch
3. reruns explain the divergence surface instead of merely reporting non-match

Proof target:
1. contract
2. integration

## Workstream 2: Promote Determinism Class And Failure Truth Through The Locked Path

Status:
1. substantially landed on the preserved canonical runtime event artifact stream

Objective:
1. make failure behavior as governed and auditable as success behavior

Actions:
1. expose determinism class on the locked runtime family and the locked proof/publication consumer
2. ensure `determinism_violation` is emitted and carried through on the locked failure-truth path when observed side effects violate declared class
3. preserve stable `snake_case` issue and violation codes
4. keep compatibility mappings fail-closed and unable to elevate determinism class
5. do this by extending existing surfaces in place rather than introducing a parallel result schema

Acceptance:
1. determinism class is visible without reading internal implementation code
2. failure semantics are replayable and explainable on the governed surface
3. stable issue codes become part of the locked operator truth

Proof target:
1. contract
2. integration

## Workstream 3: Lock S-04 Detector Authority For The First Slice

Status:
1. landed on the bounded fixture scope, with claim tier intentionally still bounded to `non_deterministic_lab_only`

Objective:
1. move bounded mechanically checkable classes toward deterministic truth first and model assistance second

Actions:
1. keep the first-pass detector authority scope fixed at `S-04`
2. keep model-assisted outputs supplementary:
   1. explanation
   2. prioritization
   3. fix suggestions
   4. surplus findings
3. improve scoring and verdict reporting so detector truth and model supplementation are clearly separated
4. add repeat evidence for verdict stability on the declared compare scope
5. new detector classes must not be admitted to this lane unless their compare scope, scoring contract, and authoritative truth surface are already frozen

Acceptance:
1. `S-04` bounded must-catch classes no longer depend on prompt luck for truth
2. model regressions do not silently erase deterministic truth on the declared scope
3. claim language remains scope-bounded and does not generalize beyond the detector's proven surface

Proof target:
1. contract
2. integration
3. live

## Workstream 4: Define The Extension Migration Boundary And Scaffolding

Status:
1. landed for this lane's bounded scope

Objective:
1. keep migration work bounded in this lane by defining the seam and scaffolding instead of shipping a full migration pack

Actions:
1. define the migration-pack boundary for follow-on work
2. choose one reference extension target that will prove the seam later
3. choose one conformance entrypoint extension authors should run
4. add a deprecation/removal table skeleton for older paths or compatibility-only seams

Acceptance:
1. migration-pack boundary is defined rather than implied
2. reference extension target is chosen
3. conformance entrypoint is chosen
4. deprecation/removal table skeleton exists
5. full migration-pack implementation remains explicitly deferred

Proof target:
1. structural
2. contract

## Workstream 5: Verification, Authority Sync, And Closeout Readiness

Status:
1. closeout-ready pending explicit operator acceptance of the staged governed bundle

Objective:
1. ensure the lane lands as governed reality instead of another future-facing narrative

Actions:
1. add targeted tests for the locked runtime family, the locked proof/publication consumer, the locked failure-truth path, and `S-04`
2. run live proof on the locked paths where live proof is required
3. update docs/spec references when implementation changes the active truth surface
4. record blockers explicitly when an artifact family cannot yet be upgraded cleanly

Acceptance:
1. code, specs, and operator-facing artifacts tell the same story
2. no release/publication claim outruns the proven scope
3. the lane is closable without leaving parallel active authority

Proof target:
1. structural
2. contract
3. integration
4. live where required

## Closeout Decision

1. The current governed staging bundle is the intended closeout proof for this lane:
   1. [benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json](benchmarks/staging/General/dg03192026_governed_evidence_bundle_2026-03-19.json)
   2. supporting runtime-family extracts and S-04 proof extracts listed in `Implementation Status`
2. No separate closeout memo is required unless the user explicitly asks for one.
3. This lane should not seek a higher claim tier as part of closeout.
   1. The closeout proof remains truthfully bounded to `non_deterministic_lab_only`.
   2. `S-04` deterministic truth is primary on the declared fixture scope, but that does not upgrade the staged/publication-facing claim for this lane.
4. If the user accepts the staged governed bundle as sufficient proof, the closeout move is:
   1. archive the cycle docs to `docs/projects/archive/techdebt/DG03192026/`
   2. remove the active `Priority Now` roadmap entry in the same change
   3. preserve any durable contracts/specs in their active canonical locations
   4. leave the staging artifact in `benchmarks/staging/` unless and until explicit publication approval is given

## Remaining To Close The Lane

1. Keep the publication-facing claim truthful:
   `STAGE-GEN-008` and its supporting bundle must remain `non_deterministic_lab_only` unless stronger repeat evidence justifies a higher tier on the same scope.
2. Record the intentional residual debt plainly at closeout:
   1. older benchmark rows still rely mostly on transition-rule mapping
   2. full extension migration-pack implementation remains deferred
   3. no second runtime-event artifact regime was introduced
3. Do not admit any new detector scope, proof consumer, or runtime artifact family into this lane unless the user explicitly reopens scope.

## Execution Order

1. freeze the Decision Lock first
2. land the locked runtime provenance family before polishing publication wording
3. land determinism class and failure truth through the locked path before expanding release claims
4. land `S-04` detector authority only after its compare scope and scoring contract remain explicit
5. define migration boundary and scaffolding only after the truth surfaces are stable enough to document canonically

## Iteration Rules

1. Keep one canonical active plan only.
2. No code starts before the Decision Lock is written into the plan and treated as frozen.
3. Do not broaden the lane into a general model-evaluation program.
4. Do not add a second provenance or claim-policy surface when an existing one can be extended.
5. For any newly upgraded artifact family, record:
   1. what the authoritative compare scope is
   2. what the authoritative operator surface is
   3. what fields are first-class now
   4. what still remains transition-rule debt
6. If a proposed change cannot name its truth surface, stop and narrow scope before implementation.
7. No new detector classes enter this lane unless compare scope, scoring contract, and authoritative truth surface are already frozen.

## Stop Conditions

1. Stop and split the lane if the first-pass scope turns into a repo-wide schema migration with no bounded proof surface.
2. Stop and split the lane if the extension pack requires a broad SDK redesign rather than a bounded migration guide and conformance path.
3. Stop and split the lane if deterministic detector expansion starts implying general capability claims beyond bounded declared classes.

## Resolved Pre-Implementation Decisions

1. The first runtime artifact family is `provenance.json` + `artifact_manifest.json` + `ExtensionRunResult`.
2. The first proof/publication consumer is `benchmarks/staging/index.json`.
3. The first failure-truth path is `determinism_violation` emitted to `agent_output/observability/runtime_events.jsonl`.
4. The first bounded detector scope is `S-04` only.
5. Migration work is deferred except for boundary/scaffolding items:
   1. migration-pack boundary defined
   2. reference extension target chosen
   3. conformance entrypoint chosen
   4. deprecation table skeleton added
