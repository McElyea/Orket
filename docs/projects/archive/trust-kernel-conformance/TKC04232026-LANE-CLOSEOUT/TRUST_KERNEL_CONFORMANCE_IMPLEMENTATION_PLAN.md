# Trust Kernel and Portable Conformance Implementation Plan

Last updated: 2026-04-23
Status: Completed 2026-04-23
Owner: Orket Core

Completion status:
Workstreams 0, 1, and 2 completed on 2026-04-23.

Requirements authority:
1. `docs/projects/archive/trust-kernel-conformance/TKC04232026-LANE-CLOSEOUT/TRUST_KERNEL_CONFORMANCE_REQUIREMENTS.md`
2. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
3. `docs/specs/PORTABLE_TRUST_CONFORMANCE_PACK_V1.md`

## Scope

Implement Workstream 1 and Workstream 2 for the Trust Kernel and Portable Conformance lane.

Active compare scope:
1. `trusted_repo_config_change_v1` only.

No additional compare scope is admitted by this plan.

Adopted:
1. finite trust-kernel model,
2. portable conformance and verifier pack.

Deferred:
1. externally useful non-AWS workflow slice,
2. `trusted_repo_manifest_change_v1` admission,
3. replay-deterministic or text-deterministic claims,
4. any new compare scope admission.

## Non-Goals

This plan does not:
1. touch AWS, Terraform, Bedrock, or remote provider live proof,
2. reopen paused governed-proof lanes,
3. admit new workflow scopes,
4. rewrite the control plane,
5. change public trust claims beyond the evidence produced by this lane.

## Proof Classification

Expected proof classifications:
1. live proof: absent; this lane does not run live provider, AWS, sandbox, or remote-service proof,
2. fixture proof: positive and negative trusted-run fixtures for `trusted_repo_config_change_v1`,
3. structural proof: side-effect-free model and verifier inspection plus import/path checks,
4. integration proof: local conformance command over supplied fixtures,
5. absent proof: replay determinism, text determinism, AWS/provider-backed proof, sandbox lifecycle proof, and new workflow-scope admission.

## Global Implementation Constraints

1. Every new rerunnable JSON output must use `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger` or `write_json_with_diff_ledger`.
2. Every new or changed proof artifact must record observed path as `primary`, `fallback`, `degraded`, or `blocked`.
3. Every new or changed proof artifact must record observed result as `success`, `failure`, `partial success`, or `environment blocker`.
4. Every new or modified test must be labeled as `unit`, `contract`, `integration`, or `end-to-end`.
5. Matching signatures, summaries, copied fixtures, logs, and projections must not replace authority-bearing input evidence or claim-bearing verifier output.

## Workstream 0 - Lane Promotion And Authority Extraction

Status: Completed 2026-04-23

Goal:
1. promote the staged requirements to a live project lane,
2. extract durable contracts,
3. update roadmap authority.

Required implementation:
1. active project folder with requirements and implementation plan,
2. durable specs under `docs/specs/`,
3. roadmap Priority Now entry pointing to this implementation plan,
4. baseline authority revalidation report confirming the current status of:
   1. `trusted_repo_config_change_v1`,
   2. `verdict_deterministic`,
   3. `trusted_run.witness_bundle.v1`,
   4. `offline_trusted_run_verifier.v1`,
   5. `governed_change_packet.v1`,
   6. `governed_change_packet_standalone_verifier.v1`,
   7. public claim limits in `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`.

Acceptance:
1. active project folder exists,
2. durable specs exist under `docs/specs/`,
3. roadmap Priority Now points to this implementation plan,
4. baseline authority revalidation report exists,
5. docs project hygiene passes,
6. extracted durable specs preserve the adopted Workstream 1 and Workstream 2 scope and do not admit Workstream 3 or any new compare scope.

Evidence:
1. `docs/projects/archive/trust-kernel-conformance/TKC04232026-LANE-CLOSEOUT/WORKSTREAM_0_BASELINE_REVALIDATION_REPORT.md`
2. `python scripts/governance/check_docs_project_hygiene.py`

## Workstream 1 - Finite Trust-Kernel Model

Status: Completed 2026-04-23

Goal:
1. implement the finite model over serialized trusted-run evidence,
2. produce stable model signatures,
3. fail closed on missing, contradictory, stale, malformed, or unsupported-claim evidence.

Required implementation:
1. model schema and loader,
2. transition and forbidden-transition evaluator,
3. invariant id mapping,
4. canonical normalization and equivalence rules,
5. signature calculation,
6. positive and negative fixtures.

Failure causes must classify:
1. missing evidence,
2. contradictory evidence,
3. stale evidence,
4. malformed evidence,
5. unsupported claim request.

Acceptance:
1. positive fixtures accept,
2. negative fixtures reject with expected reason codes,
3. equivalent fixtures produce identical signatures,
4. model signatures are not accepted as authority without the admitted verifier path,
5. structural proof shows model evaluation is side-effect free.

Evidence:
1. implementation: `scripts/proof/finite_trust_kernel_model.py`,
2. contract and structural tests: `tests/scripts/test_finite_trust_kernel_model.py`,
3. targeted proof: `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_finite_trust_kernel_model.py`,
4. adjacent proof: `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_finite_trust_kernel_model.py tests/scripts/test_first_useful_workflow_slice.py tests/scripts/test_trusted_run_witness.py tests/scripts/test_offline_trusted_run_verifier.py tests/scripts/test_trusted_scope_family_support.py`.

## Workstream 2 - Portable Conformance Pack

Status: Completed 2026-04-23

Goal:
1. package admitted verifier paths into one skeptical-evaluator command,
2. preserve underlying evidence authority,
3. expose verifier substeps and claim downgrades.

Required implementation:
1. canonical conformance command,
2. supplied-fixture verification mode,
3. generated corruption support,
4. conformance summary output with diff-ledger behavior,
5. evaluator guide,
6. positive and negative proof cases.

Negative cases must include:
1. missing final truth,
2. missing approval or operator decision,
3. missing effect evidence,
4. validator failure where validator evidence is required,
5. authority digest drift,
6. compare-scope drift,
7. projection-only evidence masquerading as authority,
8. unsupported claim request.

Acceptance:
1. one command runs the conformance pack,
2. supplied-fixture verification is read-only over authority-bearing input artifacts,
3. all positive cases pass,
4. all negative cases fail closed with expected reason codes,
5. unsupported higher claims are downgraded or blocked explicitly,
6. verifier substeps are visible in the conformance summary,
7. no AWS, remote provider, network service, or sandbox resource is required.

Evidence:
1. implementation: `scripts/proof/run_trust_conformance_pack.py`,
2. evaluator guide: `docs/guides/TRUST_KERNEL_CONFORMANCE_PACK_GUIDE.md`,
3. integration tests: `tests/scripts/test_trust_conformance_pack.py`,
4. targeted proof: `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_trust_conformance_pack.py`,
5. adjacent proof: `ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_finite_trust_kernel_model.py tests/scripts/test_trust_conformance_pack.py tests/scripts/test_first_useful_workflow_slice.py tests/scripts/test_trusted_run_witness.py tests/scripts/test_offline_trusted_run_verifier.py tests/scripts/test_trusted_scope_family_support.py`.

## Closeout Gate

Status: Completed 2026-04-23

The lane can close only when:
1. Workstream 1 and Workstream 2 acceptance conditions pass,
2. required structural, contract, and integration proof is recorded,
3. public claim wording remains bounded to the admitted compare scope and claim tier,
4. no Workstream 3 admission has occurred,
5. `python scripts/governance/check_docs_project_hygiene.py` passes.

Evidence:
1. Workstream 1 and 2 evidence sections above,
2. `trusted_repo_config_change_v1` remains the only adopted compare scope,
3. `trusted_repo_manifest_change_v1`, replay determinism, and text determinism remain deferred,
4. closeout recorded in `CLOSEOUT.md`.
