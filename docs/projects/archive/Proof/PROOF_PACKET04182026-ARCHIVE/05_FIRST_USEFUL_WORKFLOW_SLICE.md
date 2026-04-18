# First Useful Workflow Slice

Last updated: 2026-04-16
Status: Implemented and archived
Authority status: Historical staging source only. Durable authority lives at `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`; implementation archive lives at `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`.
Owner: Orket Core

## Current Shipped Baseline

ProductFlow already proves a bounded approval-governed `write_file` path and operator-review package.

That path is valuable as proof infrastructure, but it is not yet a complete external adoption story because its replay review truthfully reports missing evidence and `non_deterministic_lab_only`.

## Future Delta Proposed By This Doc

Define the first externally useful workflow slice around a real operator problem:

```text
approve and verify a local repo change under policy
```

The point is not to build a broad workflow authoring platform.
The point is to prove one workflow that another developer or team can understand without caring about Orket internals.

## What This Doc Does Not Reopen

1. It does not widen ProductFlow into a general workflow platform.
2. It does not add a new UI requirement.
3. It does not require remote provider access.
4. It does not require broad tool support.
5. It does not make every card or flow trusted-run eligible.

## Candidate Slice

The first useful workflow should:

1. start from a persisted card or flow
2. request one bounded file mutation
3. pause for operator approval
4. continue on approval or terminal-stop on denial
5. write one output artifact
6. run one deterministic validator
7. publish final truth
8. emit a trusted-run witness bundle
9. pass offline verification

## Why This Slice

This is useful to others because it maps to common real workflows:

1. generate a config change
2. update a project file
3. create or revise a small document
4. propose a controlled automation change
5. prove what changed and why it was allowed

The value is not that Orket can write a file.
The value is that Orket can prove the write was authorized, bounded, observed, and truthfully classified.

## Required Evidence

The slice should produce:

1. run input and resolved policy
2. approval request payload
3. approval resolution operator action
4. checkpoint acceptance record
5. resource reservation and lease evidence
6. effect journal entry for the mutation
7. artifact hash or state observation
8. deterministic validator result
9. final truth record
10. verifier report

## Deterministic Validator Candidates

The first validator should be mechanically checkable.

Candidate validators:

1. exact file content match for a controlled fixture
2. JSON schema validation for a generated config
3. markdown section presence for a generated doc
4. no forbidden path mutation outside an allowed directory
5. stable digest comparison for the expected output artifact

The adopted slice chose JSON schema validation for `workspace/trusted_repo_change/repo/config/trusted-change.json`.

## Minimum External Demo

The implemented demo is runnable as:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

The active implementation record is archived at `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`.

## Acceptance Boundary

This idea is complete only when an outside reviewer can answer:

1. What work was requested?
2. What changed?
3. Who or what approved it?
4. What policy governed it?
5. What evidence proves the effect?
6. What claim tier is allowed?
7. What would have failed closed if evidence were missing?
