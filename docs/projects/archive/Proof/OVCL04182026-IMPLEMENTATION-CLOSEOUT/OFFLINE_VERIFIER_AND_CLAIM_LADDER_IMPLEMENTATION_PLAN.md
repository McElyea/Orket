# Offline Verifier And Claim Ladder Implementation Plan

Last updated: 2026-04-18
Status: Completed implementation - archived
Owner: Orket Core

Accepted requirements: `docs/projects/archive/Proof/OVCL04182026-IMPLEMENTATION-CLOSEOUT/OFFLINE_VERIFIER_AND_CLAIM_LADDER_REQUIREMENTS.md`
Durable spec: `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
Contract delta: `docs/architecture/CONTRACT_DELTA_OFFLINE_TRUSTED_RUN_VERIFIER_V1_2026-04-18.md`

## Purpose

Implement the first offline claim evaluator for Trusted Run evidence.

The implementation must inspect existing witness evidence, assign the highest truthful claim tier, and report forbidden higher claims without running the workflow, calling a model, or mutating workflow state.

## Scope

In scope:

1. offline verifier module
2. CLI command
3. stable diff-ledger output
4. bundle input mode
5. single-report input mode
6. campaign-report input mode
7. future-gated replay and text identity failures
8. positive and negative contract tests
9. live campaign plus offline verifier proof

Out of scope:

1. general replay execution
2. model/provider calls
3. public publication
4. replacing Trusted Run Witness bundle verification
5. making text identity a first-slice success claim

## Work Items

1. Durable spec extraction
   - create `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
   - record contract delta
   - update authority index

2. Implementation
   - add `scripts/proof/offline_trusted_run_verifier.py`
   - add `scripts/proof/verify_offline_trusted_run_claim.py`
   - preserve existing Trusted Run Witness verifier behavior

3. Tests
   - add contract tests for bundle, single-report, and campaign-report modes
   - add requested replay downgrade proof
   - add every `OVCL-CORR-*` negative case
   - prove CLI diff-ledger output

4. Live proof
   - run `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py`
   - run `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_run_witness_verification.json --claim verdict_deterministic`

## Completion Gate

The lane can close when:

1. the durable spec exists
2. the CLI emits `offline_trusted_run_verifier.v1`
3. contract tests pass
4. the live ProductFlow Trusted Run Witness campaign succeeds
5. the offline verifier accepts that campaign report as `verdict_deterministic`
6. roadmap and authority docs are updated
