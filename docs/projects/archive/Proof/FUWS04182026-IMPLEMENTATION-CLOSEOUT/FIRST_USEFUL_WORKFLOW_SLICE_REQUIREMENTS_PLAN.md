# First Useful Workflow Slice Requirements Plan

Last updated: 2026-04-18
Status: Accepted, implemented, and archived
Owner: Orket Core

Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/05_FIRST_USEFUL_WORKFLOW_SLICE.md`
Archived requirements draft: `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/FIRST_USEFUL_WORKFLOW_SLICE_REQUIREMENTS.md`
Completed dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Completed dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
Completed dependency: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
Completed dependency: `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

## Purpose

Promote only the `First Useful Workflow Slice` idea into an active requirements lane.

This lane defines the first externally understandable workflow slice that proves Orket's trust value outside its internal control-plane story.

The first bounded product question is:

```text
Can Orket approve, perform, validate, witness, and offline-verify one useful
local repo change without claiming more than the evidence supports?
```

## Current Baseline

The lane starts from shipped or active authority:

1. ProductFlow governed `write_file` live proof
2. Trusted Run Witness v1
3. Trusted Run Invariants v1
4. Control Plane Witness Substrate v1
5. Offline Trusted Run Verifier v1
6. determinism claim policy in `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Scope

In scope:

1. define the first useful workflow's user-facing task
2. define the bounded compare scope and operator surface
3. choose the deterministic validator
4. specify evidence required from request through final truth
5. require trusted-run witness bundle generation
6. require offline verifier proof
7. require negative proof for missing approval, missing effect evidence, validator failure, and overclaim prevention

Out of scope:

1. broad workflow authoring
2. new UI work
3. remote provider dependency
4. publication claims
5. making all ProductFlow or card runs trusted-run eligible
6. claiming replay or text determinism without the evidence required by `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

## Work Items

1. Requirements hardening - complete
   - define the exact workflow task
   - define target user and practical value
   - define the bounded success statement

2. Claim surface selection - complete
   - define compare scope
   - define operator surface
   - define target claim tier and acceptable fallback tier

3. Validator selection - complete
   - choose one deterministic validator
   - define pass and fail semantics
   - define validator output schema expectations

4. Evidence contract - complete
   - list required request, policy, approval, checkpoint, lease, effect, artifact, validator, and final-truth evidence
   - identify what can be projected and what must be authority
   - identify what evidence is inherited from existing Trusted Run contracts

5. Proof plan - complete
   - define positive live proof
   - define offline verifier proof
   - define negative corruption cases
   - define output artifact paths

6. Durable spec decision - complete
   - decide whether accepted requirements become `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
   - update `CURRENT_AUTHORITY.md` only if canonical commands, paths, source-of-truth behavior, or active contracts change

## Resolved Initial Questions

1. The first useful slice should mutate a controlled fixture repo, not the Orket source tree.
2. The changed artifact should be a generated JSON config at `workspace/trusted_repo_change/repo/config/trusted-change.json`.
3. The first validator should be JSON schema validation with `const` checks for the expected values.
4. The target claim tier should remain `verdict_deterministic`; `replay_deterministic` and `text_deterministic` remain future-gated.
5. The implementation should introduce a new proof-only workflow command while reusing existing Trusted Run components where practical.
6. Denial and validator-failure examples should be live or integration proofs; missing evidence and overclaim examples should be generated corruption tests.

## Requirements Completion State

The canonical requirements draft now specifies:

1. exact workflow task
2. target user-facing value
3. compare scope and operator surface
4. target and fallback claim tiers
5. deterministic validator surface and semantics
6. required authority evidence
7. contract verdict and must-catch outcomes
8. failure semantics
9. positive and negative proof requirements
10. durable spec extraction decision

This requirements lane was accepted for implementation on 2026-04-18 by the user's `continue` request, implemented, and archived at `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`.

## Completion Gate

This requirements lane can close only when:

1. the useful workflow task is explicit and externally understandable
2. compare scope and operator surface are named
3. the deterministic validator is chosen
4. required authority evidence is listed
5. success, validator failure, denial, and missing-evidence paths are specified
6. proof artifact paths are specified
7. durable spec extraction is decided
8. the user accepts the requirements or explicitly retires the lane

The user acceptance, implementation proof, and archive conditions are satisfied.

## Remaining Open Questions

No requirements-blocking questions remain.

Implementation details such as exact CLI argument names, module placement, and whether denial and validator-failure proof are run through separate commands or command flags are intentionally deferred to the accepted implementation plan.
