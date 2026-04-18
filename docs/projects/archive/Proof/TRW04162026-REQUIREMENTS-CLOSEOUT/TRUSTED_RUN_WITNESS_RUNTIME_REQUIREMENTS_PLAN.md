# Trusted Run Witness Runtime Requirements Plan

Last updated: 2026-04-16
Status: Completed requirements lane
Owner: Orket Core

Canonical requirements draft: `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/01_TRUSTED_RUN_WITNESS_RUNTIME.md`

## Purpose

Promote only the `Trusted Run Witness Runtime` idea into an active requirements lane.

This lane defined the smallest trusted-run witness contract for Orket's next proof implementation. It did not adopt the rest of `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/`.

## Current Shipped Baseline

Orket currently has:

1. deterministic-runtime target architecture in `docs/ARCHITECTURE.md`
2. selected governed control-plane paths recorded in `CURRENT_AUTHORITY.md`
3. governed start-path authority in `docs/specs/CONTROL_PLANE_GOVERNED_START_PATH_MATRIX.md`
4. determinism claim tiers in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
5. minimum auditable record rules in `docs/specs/MINIMUM_AUDITABLE_RECORD_V1.md`
6. ProductFlow governed execution and review-package specs in `docs/specs/PRODUCTFLOW_GOVERNED_RUN_WALKTHROUGH_V1.md` and `docs/specs/PRODUCTFLOW_OPERATOR_REVIEW_PACKAGE_V1.md`

The ProductFlow baseline remains truthful but incomplete as a trusted-run claim because current replay review may report `replay_ready=false`, `stability_status=not_evaluable`, and `claim_tier=non_deterministic_lab_only`.

## Scope

In scope:

1. define `Trusted Run Witness v1` terms and bundle requirements
2. define the minimum required authority lineage for one bounded governed run
3. define claim-tier, compare-scope, and operator-surface requirements
4. define negative verification expectations for missing or corrupted evidence
5. record the decision to extend ProductFlow instead of starting a proof-specific fixture
6. identify which durable specs must be extracted before implementation

Out of scope:

1. implementing the witness bundle
2. implementing the offline verifier
3. widening control-plane coverage
4. adopting the other proof-packet ideas
5. publishing public claims
6. moving to implementation during this requirements lane

## Work Items

1. Requirements hardening
   - complete; `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS.md` names the first slice, claim surface, required authority matrix, and proof expectations

2. First-slice decision
   - complete; first slice extends ProductFlow governed `write_file`
   - bounded effect is `agent_output/productflow/approved.txt`
   - deterministic verdict surface is `trusted_run_contract_verdict.v1`

3. Authority matrix
   - complete; required authority, optional support surfaces, forbidden substitutes, and failure semantics are listed in the requirements draft

4. Claim surface
   - complete; initial `compare_scope` is `trusted_run_productflow_write_file_v1`
   - initial `operator_surface` is `trusted_run_witness_report.v1`
   - target claim tier is `verdict_deterministic`
   - allowed lower-tier fallback is `non_deterministic_lab_only`

5. Spec extraction decision
   - complete; durable contract material must be extracted into `docs/specs/TRUSTED_RUN_WITNESS_V1.md` before implementation
   - `CURRENT_AUTHORITY.md` changes are required only when implementation changes behavior or source-of-truth paths

## Completion Gate

This requirements lane can close only when:

1. the user accepts the requirements or explicitly retires the lane
2. the requirements name one first trusted-run slice
3. the requirements name the initial compare scope and operator surface
4. the requirements state proof expectations and negative verification expectations
5. remaining implementation decisions are listed explicitly

This requirements lane is not implementation-complete merely because an implementation plan later exists. Requirements stay active until the user accepts them and explicitly asks for implementation or retirement.

Current completion state:

1. requirements name one first trusted-run slice
2. requirements name the initial compare scope and operator surface
3. requirements state proof expectations and negative verification expectations
4. remaining implementation decisions are listed explicitly
5. user acceptance completed by explicit Priority Now completion request on 2026-04-16

## Promotion Rule

If the user accepts these requirements for implementation:

1. extract durable contract material into `docs/specs/` where needed
2. create a bounded implementation plan
3. update `docs/ROADMAP.md` to point at the implementation plan
4. update `CURRENT_AUTHORITY.md` only when behavior or source-of-truth authority changes

## Closeout

This requirements lane is closed and archived at `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/`.

The next implementation step is not active by implication. It requires an explicit implementation request and must begin by extracting durable contract material into `docs/specs/TRUSTED_RUN_WITNESS_V1.md`.
