# Trusted Run Witness Runtime Implementation Plan

Last updated: 2026-04-16
Status: Completed implementation lane
Owner: Orket Core

Spec authority: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Accepted requirements archive: `docs/projects/archive/Proof/TRW04162026-REQUIREMENTS-CLOSEOUT/TRUSTED_RUN_WITNESS_RUNTIME_REQUIREMENTS.md`
Closeout: `docs/projects/archive/Proof/TRW04162026-IMPLEMENTATION-CLOSEOUT/CLOSEOUT.md`

## Purpose

Implement the accepted Trusted Run Witness Runtime plan for the bounded ProductFlow governed `write_file` slice.

This lane turned the accepted requirements into:

1. a durable `Trusted Run Witness v1` spec
2. a witness bundle rooted at `runs/<session_id>/trusted_run_witness_bundle.json`
3. a side-effect-free verifier for `trusted_run_witness_report.v1`
4. a two-run campaign that can truthfully claim `verdict_deterministic`

## Scope

In scope:

1. extend ProductFlow governed `write_file`; do not create a second golden path
2. keep the ProductFlow turn-tool `run_id` as canonical identity
3. record required authority lineage from the approval, checkpoint, resource, effect-journal, and final-truth surfaces
4. verify exact output path, normalized content, issue status, final truth, and authority-lineage alignment
5. write the canonical verifier proof output at `benchmarks/results/proof/trusted_run_witness_verification.json`

Out of scope:

1. full offline replay determinism
2. byte-identical text determinism
3. public publication claims
4. universal trusted-run coverage for all Orket workflows

## Completed Work

1. Extracted durable contract
   - spec: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`

2. Implemented witness bundle builder
   - script: `scripts/proof/build_trusted_run_witness_bundle.py`
   - default bundle root: `runs/<session_id>/trusted_run_witness_bundle.json`

3. Implemented side-effect-free verifier
   - script: `scripts/proof/verify_trusted_run_witness_bundle.py`
   - canonical proof output: `benchmarks/results/proof/trusted_run_witness_verification.json`

4. Implemented repeat campaign
   - script: `scripts/proof/run_trusted_run_witness_campaign.py`
   - runs ProductFlow twice with sandbox disabled for routine proof
   - upgrades only stable equivalent verdicts to `verdict_deterministic`

5. Added contract tests
   - schema validation
   - authority-lineage id drift
   - missing final truth
   - missing contract verdict
   - wrong output content
   - two-report verdict-stability claim

## Completion Gate Result

Completed on 2026-04-16.

1. contract tests passed
2. the two-run campaign wrote `benchmarks/results/proof/trusted_run_witness_verification.json`
3. the verifier proof output recorded `observed_path=primary`
4. the verifier proof output recorded `observed_result=success`
5. the verifier proof output recorded `claim_tier=verdict_deterministic`
