# Workstream 0 Baseline Revalidation Report

Last updated: 2026-04-23
Status: Completed
Owner: Orket Core

## Purpose

Record the baseline authority revalidation required before Trust Kernel and Portable Conformance Workstreams 1 and 2 may begin.

Proof classification: structural/docs authority revalidation.
Observed path: primary.
Observed result: success.

## Scope

This report validates Workstream 0 only.
It does not run verifier commands, replay commands, model/provider calls, AWS flows, sandbox flows, or runtime tests.

## Sources Checked

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`
4. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`
5. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
6. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
7. `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md`
8. `docs/projects/trust-kernel-conformance/TRUST_KERNEL_CONFORMANCE_REQUIREMENTS.md`
9. `docs/projects/trust-kernel-conformance/TRUST_KERNEL_CONFORMANCE_IMPLEMENTATION_PLAN.md`
10. `docs/ROADMAP.md`

## Baseline Findings

### `trusted_repo_config_change_v1`

Status: confirmed current public trust compare scope.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `trusted_repo_config_change_v1` as the admitted external trust slice compare scope.
2. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` names `trusted_repo_config_change_v1` as the useful workflow slice compare scope.
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` includes `trusted_repo_config_change_v1` as an admitted First Useful Workflow Slice identity.

### `verdict_deterministic`

Status: confirmed current truthful claim ceiling for the public trust slice.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `verdict_deterministic` as the current claim tier ceiling.
2. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` names `verdict_deterministic` as the target claim tier.
3. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` allows `verdict_deterministic` only from stable campaign evidence for this scope.

### `trusted_run.witness_bundle.v1`

Status: confirmed current witness bundle schema.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `trusted_run.witness_bundle.v1` as the witness bundle schema.
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md` defines the bundle schema and required bundle fields.
3. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` requires the witness bundle as authority evidence.

### `offline_trusted_run_verifier.v1`

Status: confirmed current offline verifier report schema.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `offline_trusted_run_verifier.v1` as the offline verifier report schema.
2. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md` defines the report schema and claim ladder.
3. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` requires the offline verifier report for claim assignment proof.

### `governed_change_packet.v1`

Status: confirmed current governed change packet schema for the public trust slice.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `governed_change_packet.v1` as the governed change packet schema.
2. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` requires the governed change packet as the primary outside-operator packet path.
3. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md` defines its verifier over `governed_change_packet.v1`.

### `governed_change_packet_standalone_verifier.v1`

Status: confirmed current standalone packet verifier schema.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` names `governed_change_packet_standalone_verifier.v1` as the standalone packet verifier schema.
2. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md` defines the admitted verifier surface.
3. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` requires a packet verifier report for standalone packet verification.

### Public Claim Limits

Status: confirmed public claim limits remain bounded.

Evidence:
1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` requires public wording for this slice to name the compare scope, current truthful claim ceiling, missing replay determinism, missing text determinism, and proof-only fixture-bounded posture.
2. The same spec forbids claims that all Orket workflows are trusted-run eligible, all Orket runs are deterministic, the current slice proves model output correctness, the current slice proves replay determinism, or the current slice proves text determinism.

## Extracted Durable Spec Boundary Check

Status: passed.

Findings:
1. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md` adopts only the finite trust-kernel model workstream.
2. `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md` adopts only the portable conformance pack workstream.
3. Both specs name existing `trusted_repo_config_change_v1` as the initial admitted compare scope.
4. Both specs keep `trusted_repo_manifest_change_v1` deferred as a preferred future candidate only.
5. Both specs state they do not admit a new workflow scope by themselves.
6. Both specs do not claim replay determinism or text determinism.

## Workstream 0 Acceptance Mapping

| Acceptance item | Result | Evidence |
|---|---|---|
| active project folder exists | passed | `docs/projects/trust-kernel-conformance/` |
| durable specs exist under `docs/specs/` | passed | `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`, `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md` |
| roadmap Priority Now points to implementation plan | passed | `docs/ROADMAP.md` |
| baseline authority revalidation report exists | passed | this report |
| docs project hygiene passes | passed | `python scripts/governance/check_docs_project_hygiene.py` |
| extracted specs preserve WS1/WS2 scope and do not admit WS3 or any new compare scope | passed | extracted durable spec boundary check above |

## Conclusion

Workstream 0 acceptance is complete.
Workstreams 1 and 2 may proceed under `docs/projects/trust-kernel-conformance/TRUST_KERNEL_CONFORMANCE_IMPLEMENTATION_PLAN.md`.
