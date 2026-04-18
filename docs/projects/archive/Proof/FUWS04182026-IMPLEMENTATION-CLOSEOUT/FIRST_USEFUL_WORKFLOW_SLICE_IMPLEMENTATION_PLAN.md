# First Useful Workflow Slice Implementation Plan

Last updated: 2026-04-18
Status: Completed and archived
Owner: Orket Core

Accepted requirements: `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/FIRST_USEFUL_WORKFLOW_SLICE_REQUIREMENTS.md`
Durable contract: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
Contract delta: `docs/architecture/CONTRACT_DELTA_FIRST_USEFUL_WORKFLOW_SLICE_V1_2026-04-18.md`

## Purpose

Implement the accepted First Useful Workflow Slice requirements without relabeling the existing ProductFlow `approved.txt` proof.

The bounded implementation goal is:

```text
Run a proof-only workflow that approves, writes, validates, witnesses, campaigns,
and offline-verifies one controlled fixture repo JSON config change.
```

## Scope

In scope:

1. proof-only trusted repo change workflow command
2. deterministic config validator
3. dedicated contract verdict for `trusted_repo_change_contract_verdict.v1`
4. witness bundle generation using `trusted_run.witness_bundle.v1`
5. witness report and campaign report using `trusted_run_witness_report.v1`
6. offline verifier routing for `trusted_repo_config_change_v1`
7. positive, denial, validator-failure, corruption, and overclaim tests
8. live campaign proof and offline verifier proof
9. same-change authority and roadmap closeout

Out of scope:

1. broad workflow authoring
2. UI integration
3. remote provider dependency
4. mutation of the Orket source tree
5. replay or text deterministic claims

## Work Items

1. Durable contract extraction - complete
   - create `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
   - record contract delta
   - update affected Trusted Run and offline verifier specs

2. Proof workflow implementation - complete
   - add `scripts/proof/run_trusted_repo_change.py`
   - add `scripts/proof/run_trusted_repo_change_campaign.py`
   - keep mutations bounded to `workspace/trusted_repo_change/`

3. Validator and witness implementation - complete
   - implement `trusted_repo_config_validator.v1`
   - implement `trusted_repo_change_contract_verdict.v1`
   - implement invariant and substrate signatures for the new compare scope

4. Offline claim routing - complete
   - preserve ProductFlow verifier behavior
   - route `trusted_repo_config_change_v1` through the new evaluator
   - keep higher unsupported claims downgraded or blocked

5. Verification - complete
   - run targeted contract and integration tests
   - run live approved campaign proof
   - run live or integration denial proof
   - run live or integration validator-failure proof
   - run offline verifier proof

6. Closeout - complete
   - update `CURRENT_AUTHORITY.md`
   - update `docs/ROADMAP.md` and project index
   - update future packet status
   - archive active lane docs
   - run docs project hygiene

## Completion Gate

This lane is complete only when:

1. the approved workflow writes the expected fixture config and emits proof artifacts
2. denial terminal-stops before mutation
3. validator failure blocks success final truth
4. at least two equivalent successful runs produce stable verdict, validator, invariant, substrate, and must-catch signatures
5. offline verifier allows `verdict_deterministic` for the campaign
6. replay and text deterministic overclaims fail closed
7. live proof and docs hygiene results are recorded at handoff

All completion gates were satisfied on 2026-04-18. Closeout authority: `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/FIRST_USEFUL_WORKFLOW_SLICE_CLOSEOUT.md`.
