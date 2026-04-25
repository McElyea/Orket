# Trust Kernel and Portable Conformance Requirements

Last updated: 2026-04-23
Status: Completed lane requirements
Authority status: Archived with completed trust-kernel-conformance lane closeout
Owner: Orket Core
Lane family: Trust proof and external adoption

## Purpose

Define the adopted requirements for the Trust Kernel and Portable Conformance lane.

The lane goal is not to claim that Orket is mathematically proven in general.
The lane goal is to make this bounded claim stronger, clearer, and more useful:

```text
For admitted workflow scopes, Orket can reduce a run to a finite evidence model,
verify required invariants offline, cap claims to the highest proven tier, and
fail closed when authority evidence is missing or contradictory.
```

## Adopted Scope

This active lane adopts:
1. Workstream 1: finite trust-kernel model,
2. Workstream 2: portable conformance and verifier pack.

This active lane defers:
1. Workstream 3: externally useful non-AWS workflow slice.

The preferred future Workstream 3 candidate remains `trusted_repo_manifest_change_v1`, but that scope is not admitted by this lane.

## Durable Contracts

The adopted durable contracts are:
1. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`,
2. `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md`.

Supporting existing contracts include:
1. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`,
2. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`,
3. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`,
4. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`,
5. `docs/specs/GOVERNED_CHANGE_PACKET_STANDALONE_VERIFIER_V1.md`,
6. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`,
7. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

## Current Shipped Baseline

Current authority already ships a narrow externally admitted trust story.
That baseline includes:
1. admitted public compare scope `trusted_repo_config_change_v1`,
2. truthful claim ceiling `verdict_deterministic`,
3. `trusted_run.witness_bundle.v1` evidence,
4. `offline_trusted_run_verifier.v1` claim assignment,
5. `governed_change_packet.v1` as the operator entry artifact,
6. `governed_change_packet_standalone_verifier.v1` packet verification,
7. explicit public claim limits in `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

That baseline is proof-only and fixture-bounded.
It does not prove broad workflow determinism, replay determinism, text determinism, arbitrary model correctness, or arbitrary workflow trust.
This baseline must be revalidated against current authority before implementation changes rely on it.

## What This Lane Does Not Reopen

This lane does not reopen:
1. Terraform or other AWS/provider-backed admission,
2. paused governed-proof lanes,
3. broad ControlPlane convergence,
4. replay-deterministic or text-deterministic claims without new evidence satisfying `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`,
5. broad claims that all Orket workflows are trusted-run eligible,
6. public wording that Orket is mathematically sound without a bounded compare scope,
7. model or prompt quality work as a substitute for verifier evidence,
8. new workflow-scope admission.

## Requirements

TKC-R-001. Implement the finite evidence model required by `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`.

TKC-R-002. Implement the portable conformance pack required by `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md`.

TKC-R-003. Preserve the initial compare scope as existing `trusted_repo_config_change_v1`.

TKC-R-004. Do not admit `trusted_repo_manifest_change_v1` or any other new workflow scope in this lane.

TKC-R-005. Keep finite-model signatures claim-supporting only.
They must not replace witness authority, validator authority, offline verifier claim output, or packet verifier claim output.

TKC-R-006. Define evidence equivalence through canonical normalization, not implementation-local comparison logic.

TKC-R-007. Supplied-fixture verification mode must be read-only over authority-bearing input artifacts.

TKC-R-008. Generated corruptions must preserve a reference to the original positive fixture and identify the exact corruption applied.

TKC-R-009. The conformance command must expose its verifier substeps, input artifact paths, output artifact paths, and downgrade reasons.

TKC-R-010. Every new rerunnable JSON output must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.

TKC-R-011. Every new or changed proof artifact must record observed path as `primary`, `fallback`, `degraded`, or `blocked`.

TKC-R-012. Every new or changed proof artifact must record observed result as `success`, `failure`, `partial success`, or `environment blocker`.

TKC-R-013. Every new or modified test must be labeled as `unit`, `contract`, `integration`, or `end-to-end`.

TKC-R-014. New public trust wording must be claim-tier and compare-scope explicit.

TKC-R-015. The lane must report unresolved proof gaps as blockers or drift, not as future confidence.

## Acceptance Boundary

This lane is acceptable only when:
1. the finite model has a stable schema and side-effect-free proof,
2. positive fixtures accept and negative fixtures fail closed with expected reason codes,
3. equivalent accepted fixtures produce stable finite-model signatures,
4. supplied-fixture verification is read-only over authority-bearing input artifacts,
5. the conformance pack exposes verifier substeps,
6. unsupported higher claims are downgraded or blocked explicitly,
7. fixture-only proof is not presented as live proof,
8. no new workflow scope is admitted.

## Proof Requirements

Structural proof:
1. model evaluation is side-effect free,
2. model signatures are not accepted as authority without the admitted verifier path,
3. supplied-fixture verification does not mutate authority-bearing input artifacts.

Contract proof:
1. conformance summary schema validation,
2. positive fixture acceptance,
3. negative fixture rejection,
4. claim downgrade behavior,
5. diff-ledger output behavior,
6. canonical normalization defines evidence equivalence.

Integration proof:
1. the canonical conformance command runs from a clean local checkout,
2. no AWS, remote provider, network service, or sandbox resource is required,
3. verifier substeps and artifact refs are visible in the conformance summary.
