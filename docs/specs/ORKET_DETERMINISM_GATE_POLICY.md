# Orket Determinism Gate Policy

Last updated: 2026-03-19
Status: Active
Owner: Orket Core

This document operationalizes [docs/specs/ORKET_OPERATING_PRINCIPLES.md](docs/specs/ORKET_OPERATING_PRINCIPLES.md) for determinism claims, promotion decisions, and publication language.

It does not replace:
1. [docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md](docs/specs/PROTOCOL_DETERMINISM_CONTROL_SURFACE.md)
2. [docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md](docs/specs/PROTOCOL_REPLAY_CAMPAIGN_SCHEMA.md)
3. [docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md](docs/specs/PROTOCOL_LEDGER_PARITY_CAMPAIGN_SCHEMA.md)
4. [docs/specs/OFFLINE_CAPABILITY_MATRIX.md](docs/specs/OFFLINE_CAPABILITY_MATRIX.md)
5. [docs/specs/CORE_RELEASE_GATE_CHECKLIST.md](docs/specs/CORE_RELEASE_GATE_CHECKLIST.md)
6. [docs/process/PUBLISHED_ARTIFACTS_POLICY.md](docs/process/PUBLISHED_ARTIFACTS_POLICY.md)
7. [docs/process/PRODUCT_PUBLISHING.md](docs/process/PRODUCT_PUBLISHING.md)

This policy defines:
1. what determinism tier Orket may claim,
2. what gate a result must pass before that claim is allowed,
3. what scope and control surfaces must bound the claim.

## Purpose

Orket's deterministic story belongs at the contract and verdict layers before it belongs at the raw prose layer.

The system should primarily prove that:
1. governed inputs can be replayed honestly,
2. verdicts and must-catch outcomes remain stable on the declared compare scope,
3. text identity is claimed only when byte-level proof exists on that same scope.

Model or prompt choice is an input to this governed system. It is not the primary source of truth.

## Definitions

`compare_scope`
1. the bounded claim domain on which determinism is being asserted
2. examples: a replay campaign, a benchmark verdict family, or a named workload fixture set

`operator_surface`
1. the actual artifact or comparison surface used to evaluate the claim
2. examples: replay receipts, ledger parity summaries, score reports, or declared output hashes

`control_bundle`
1. the captured set of inputs and runtime controls that materially affect the claim
2. examples: prompt selection policy, model/provider selection, runtime policy, environment control surface, and network/time/locale controls where applicable

## Scope

This policy applies to:
1. model and prompt evaluation lanes,
2. workload proof artifacts,
3. replay and parity campaigns,
4. benchmark and publication artifacts,
5. release and promotion wording that makes determinism claims.

## Claim Tiers

Allowed `claim_tier` values:

1. `replay_deterministic`
   - Same governed input bundle and declared control surface can be replayed and compared honestly on the declared operator surface.
2. `verdict_deterministic`
   - Wording may vary, but the scored verdict, must-catch set, and policy decision remain stable on the declared compare scope.
3. `text_deterministic`
   - Raw output bytes or output hash are identical on the declared compare scope.
4. `non_deterministic_lab_only`
   - Result may still be useful for exploration, but it is not eligible for product or publication claims beyond lab labeling.

Rules:
1. Claims default to the lowest proven tier.
2. `text_deterministic` must not be claimed unless `replay_deterministic` or `verdict_deterministic` is also proven on the same compare scope.
3. Product and release claims must stop at `replay_deterministic` or `verdict_deterministic` unless byte-level identity is explicitly required by the supported capability and separately proven.
4. A claim is invalid if it omits the compare scope that bounds its meaning.

## Minimum Evidence by Claim Tier

### `replay_deterministic`

Requires:
1. at least one governed replay artifact on the named operator surface
2. successful comparison on the declared compare scope
3. captured or linked control bundle
4. no unresolved contradiction between replay evidence and the human-facing claim

### `verdict_deterministic`

Requires:
1. repeat evidence from at least two executions or a campaign artifact
2. stable scored verdict on the declared compare scope
3. stable must-catch outcome set on that scope
4. wording drift, if present, is explicitly treated as non-blocking unless the compare scope includes prose identity

### `text_deterministic`

Requires:
1. all evidence required for `replay_deterministic` or `verdict_deterministic`
2. byte-identical output or identical declared output hash
3. explicit declaration of the bytes or hashes in scope

### `non_deterministic_lab_only`

Requires:
1. lab labeling
2. captured control surface
3. no release or publication claim beyond lab status

## Required Claim Surfaces

Every serious proof, release, or publication artifact must carry or explicitly map the following surfaces:

1. `claim_tier`
2. `compare_scope`
3. `operator_surface`
4. `policy_digest`
5. `control_bundle_ref` or `control_bundle_hash`
6. model/provider/prompt selection metadata
7. evidence artifact path or canonical evidence reference

`policy_digest` must identify the governing policy/configuration set that materially affects the claim, including applicable prompt selection policy, scoring policy, detector policy, and runtime policy where relevant.

`compare_scope` must be concrete. Examples:
1. `protocol_replay_campaign`
2. `protocol_ledger_parity_campaign`
3. `benchmark_verdict_stability`
4. `workload_s04_fixture_v1`

`operator_surface` must name the actual compare surface. Examples:
1. replay receipts
2. ledger parity summary
3. benchmark score report
4. workload answer-key scoring verdict

## Current-State Transition Rule

Some current artifacts do not yet expose all required claim surfaces as first-class fields.

Until result schemas are upgraded:
1. proof and release artifacts may satisfy this policy by an explicit closeout or publication mapping that names the required surfaces,
2. publication wording must still state the `claim_tier` and `compare_scope`,
3. missing first-class fields are treated as schema debt, not permission to overclaim.

This transition rule does not allow omission of scope in human-facing claims.
The transition rule is temporary. New proof, release, and publication artifact schemas must expose required claim surfaces as first-class fields, and mapping-only compliance must not be used for newly introduced artifact families.
This policy creates schema debt until each governed artifact family exposes `claim_tier`, `compare_scope`, `operator_surface`, and control-bundle linkage as first-class fields.

## Gate Stack

### `L1` Lab Gate

Purpose:
1. explore models, prompts, contexts, and methods without turning experiments into product truth

Belongs here:
1. local-model sweeps
2. prompt profile experiments
3. quant/thermal/VRAM investigations
4. prototype selectors
5. alternate decomposition or guard strategies

Lab requirements:
1. artifacts must be labeled lab
2. control surfaces must be captured
3. prompt policy/version and model config must be recorded
4. failures must remain visible and fail-closed behavior must not be hidden

Lab pass criteria:
1. contract-valid outputs where applicable
2. no safety or offline-default regression on the explored path
3. determinism metrics are recorded, even if poor

Lab failure rule:
1. interesting results may remain `non_deterministic_lab_only`
2. lab success alone does not justify release or publication proof

### `P1` Proof Gate

Purpose:
1. prove that a capability claim is real on a bounded, named surface

Proof requirements:
1. the capability has a canonical operator surface
2. the compare scope is explicit
3. the determinism control surface is captured or linked
4. replay, parity, repeatability, or verdict-stability evidence exists
5. deterministic detectors are primary or explicitly designated co-equal evidence for bounded canonical must-catch classes when such classes are declared

Proof pass criteria:
1. the claimed `claim_tier` is directly supported by the evidence
2. repeated runs or campaign evidence demonstrate stability on the declared compare scope
3. fail-closed behavior is preserved where relevant
4. deterministic must-catch classes do not silently regress

Proof failure rule:
1. model-only success does not rescue missing deterministic proof for bounded must-catch classes
2. deterministic and model-assisted disagreement must be reported, not averaged into truth, and release/publication claims must resolve which surface is authoritative for the declared class
3. single-run success without repeat evidence is not a determinism proof

### `R1` Release Gate

Purpose:
1. decide whether a capability is allowed to ship as part of supported Orket behavior

Release requirements:
1. a passing proof artifact already exists
2. required CI gates are green
3. offline-default and fail-closed expectations remain green
4. replay/parity/scoring gates required by the touched surface remain green
5. docs and implementation do not contradict the claim being shipped

Release pass criteria:
1. the release claim names its `claim_tier`
2. the release claim names its `compare_scope`
3. no experimental model or prompt is the sole ungoverned reason the feature works
4. fallback, degraded, and blocked behavior are explicitly represented

Release model rule:
1. model sweeps rank only already-eligible candidates
2. a model enters the release candidate pool only after the capability gates pass

### `PUB1` Publication Gate

Purpose:
1. decide what Orket is allowed to say publicly

Publication requirements:
1. the artifact already passed the Release Gate
2. the artifact is curated and share-safe
3. the claim wording matches the actual `claim_tier`
4. manual review is complete
5. explicit approval is recorded before publication

Publication pass criteria:
1. the artifact answers what it proves in one sentence
2. `claim_tier` and `compare_scope` are named
3. key signals are listed
4. model id stays metadata unless the artifact is explicitly a lab/model-comparison artifact
5. every published claim has a provenance path back to the underlying proof bundle

Publication naming rule:
1. prefer capability-first names such as `protocol_replay_parity`, `runtime_stability_proof`, or `verdict_stability`
2. do not make model names the product headline for governed capability claims

## Promotion Rules

Promotion is one-way:

1. `L1 -> P1`
   - only when the capability has a canonical operator surface, explicit compare scope, and repeatable verdict or replay evidence
2. `P1 -> R1`
   - only when required CI, replay/parity, scoring, offline-default, and truthful-doc gates pass
3. `R1 -> PUB1`
   - only when the artifact is curated, share-safe, manually reviewed, explicitly approved, and wording matches the proven claim tier

Demotion rule:
1. if a changed prompt, model, provider, or control bundle invalidates the proven scope, the result falls back to `L1` until proof is rerun

## Deterministic Detector Rule

For declared canonical must-catch classes:
1. deterministic detectors should be primary for proof-stage truth when the class is bounded and mechanically checkable
2. model-assisted review may explain, prioritize, or add surplus findings
3. deterministic detectors must be primary for release and publication truth when the class is bounded and mechanically checkable
4. model-assisted review must not be the sole basis for truth where deterministic checks exist on the declared compare scope

This rule is scope-bounded:
1. a fixture-specific or workload-specific detector is not permission to generalize the claim outside its declared compare scope

## Prompt and Model Governance Rule

Prompts are governed inputs, not the primary truth source.

Rules:
1. prompt tuning is justified for contract-adherence or bounded coverage failures
2. prompt changes do not upgrade the claim tier by themselves
3. model changes do not upgrade the claim tier by themselves
4. prompt and model sweeps must remain subordinate to capability gates

## Prohibited Claim Patterns

Orket must not:
1. say `deterministic` without naming a `claim_tier`
2. say `deterministic` without naming a `compare_scope`
3. treat lab leaderboards as release proof
4. present byte-identical prose as the default required claim for product behavior
5. let model choice become the public identity of a governed runtime capability

## Scope Transfer Rule

Proof at one `compare_scope` or `operator_surface` does not upgrade claims on another scope or surface unless separately evidenced.

Derived artifacts may inherit `claim_tier`, `compare_scope`, `operator_surface`, and control-bundle linkage only by explicit reference to a canonical parent artifact. Inheritance must be declared, not assumed.

## Authority Resolution Rule

For any governed capability claim:
1. the declared `compare_scope` determines the relevant truth surface
2. the declared `operator_surface` determines what is actually compared
3. deterministic detectors govern bounded mechanically checkable classes on that scope
4. model-assisted outputs are supplementary unless the declared scope explicitly defines them as primary evidence

## Non-Goals

This document does not:
1. define contributor workflow mechanics
2. replace release checklists or publication process docs
3. require prose identity for every supported capability
4. claim that fixture-scoped deterministic detectors are automatically general solutions
