# Outward Run Policy-Rejection Fixture Implementation Plan

Last updated: 2026-05-02
Status: Active scoped implementation lane
Owner: Orket Core

Parent umbrella lane: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`
Accepted requirements: `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-POLICY-REJECTION-FIXTURE-CLOSEOUT/POLICY_REJECTION_FIXTURE_REQUIREMENTS_V1.md`
Base closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`
Completed denial closeout: `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-DENIAL-FIXTURE-CLOSEOUT/`

## Acceptance Record

The user explicitly requested on 2026-05-02 that the outward proof-kernel extensions lane reopen only for policy-rejection fixture implementation, with a slice-scoped active plan and a roadmap entry pointing to this plan.

This activation covers only the policy-rejection fixture slice. It does not activate out-of-scope proposal rejection, multi-turn sequence proof, ODR determinism, claim posture widening, or retirement of the umbrella extension lane.

## Purpose

Create a real governed policy-rejection witness package and make the offline proof kernel accept the bounded claim:

```text
For outward_run_write_file_policy_rejected_v1, a model-produced write_file proposal was rejected by policy before approval or tool invocation, and no tool effect or commitment occurred after the policy rejection.
```

This slice covers an admitted `write_file` governed-tool proposal whose args fail `write_file` policy validation, such as workspace containment. It does not cover a model proposing an unadmitted tool, unknown tool, or non-contract tool family; that remains the deferred out-of-scope proposal fixture.

The lane closes only when the package is produced from a real governed outward path, verifies offline from package-local bytes, and activates `ORP-CORR-031` as a falsifiable corruption instead of a missing-fixture blocker.

## Non-Goals

1. out-of-scope proposal fixture generation;
2. multi-turn sequence proof;
3. ODR determinism integration;
4. public trust wording;
5. claim posture above `outward_lab_only`;
6. umbrella lane retirement.

## Implementation Rules

1. Accepted proof requires `--package`; bundle-only JSON remains introspection-only.
2. The offline verifier may read only package-local `manifest.json`, `outward_witness_bundle.json`, `ledger_export.json`, and declared package-local evidence.
3. Policy-rejection packages must not fabricate committed artifact bytes or approval authority.
4. Absence claims require full `ledger_export.v1` bytes with `export_scope=all`.
5. Existing approved-path and denial-path verification and corruption behavior must remain green.
6. The implemented policy-rejection path must remain distinct from the deferred out-of-scope proposal fixture.
7. The policy-rejected proposal identity is the tuple `(run_id, turn, tool_name, tool_args_hash)`, represented in package evidence as `proposal_ref = "model_proposal:<run_id>:<turn>:<tool_name>:<tool_args_hash>"`.

## Cuts

### Cut 1 - Contract Delta

Target files:
1. `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-POLICY-REJECTION-FIXTURE-CLOSEOUT/POLICY_REJECTION_FIXTURE_REQUIREMENTS_V1.md`
2. `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-POLICY-REJECTION-FIXTURE-CLOSEOUT/POLICY_REJECTION_FIXTURE_IMPLEMENTATION_PLAN.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/ROADMAP.md`
5. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
6. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`
7. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`
8. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`

Requirements:
1. admit `outward_run_write_file_policy_rejected_v1`;
2. define policy-rejection package artifact rules with no `committed_output`;
3. define the package-local authority evidence required for policy rejection;
4. define `proposal_ref` and the policy-rejected proposal identity tuple `(run_id, turn, tool_name, tool_args_hash)`;
5. activate ORP-INV-014 and ORP-INV-022 for policy-rejection packages;
6. keep policy-rejection single-package posture capped at `outward_lab_only`;
7. keep current authority clear that policy-rejection implementation is active, but proof authority remains blocked until the package fixture exists and verifies.

Verification:
1. `python scripts/governance/check_docs_project_hygiene.py`;
2. `git diff --check`.

### Cut 2 - Real Policy-Rejection Path Selection

Target files:
1. `orket/application/services/outward_run_execution_service.py`
2. `scripts/proof/run_outward_write_file_policy_rejected_proof.py`
3. `tests/application/test_outward_run_execution_service.py`

Requirements:
1. identify or add the smallest normal outward path that can reject a `write_file` proposal by policy before approval;
2. originate the proof run from normal outward submission rather than hand-authored package bytes;
3. set `ORKET_DISABLE_SANDBOX=1` for routine proof execution;
4. record the exact policy reason in durable run evidence and ledger events;
5. record a stable `proposal_ref` for the policy-rejected proposal;
6. stop if the only feasible rejection path is actually the deferred out-of-scope fixture.

Verification:
1. integration: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_policy_rejected_proof.py`;
2. unit or integration: policy rejection records no approval, tool invocation, or commitment.

### Cut 3 - Package Builder and Loader Support

Target files:
1. `scripts/proof/outward_run_witness_contract.py`
2. `scripts/proof/outward_run_witness_package.py`
3. `scripts/proof/outward_run_witness_builder.py`
4. `scripts/proof/emit_outward_run_witness_package.py`
5. `tests/scripts/test_emit_outward_run_witness_package.py`
6. `tests/scripts/test_outward_run_witness_package.py`

Requirements:
1. support `outward_run_write_file_policy_rejected_v1` as an admitted compare scope;
2. emit a package with full ledger export, run authority, model evidence, `proposal_ref`, and policy-rejection authority evidence;
3. omit committed artifact refs and approval authority for policy-rejected packages;
4. fail closed if a policy-rejected package has approval, tool result, or committed artifact refs for the rejected proposal.

Verification:
1. unit: loader accepts minimal policy-rejection package without artifact refs;
2. contract: producer emits policy-rejection package layout from a seeded policy-rejected run;
3. contract: producer rejects policy-rejection packages with approval or effect artifacts.

### Cut 4 - Verifier and Invariant Checker

Target files:
1. `scripts/proof/outward_run_invariant_checker.py`
2. `scripts/proof/verify_outward_run_witness_package.py`
3. `tests/scripts/test_outward_run_invariant_checker.py`
4. `tests/scripts/test_verify_outward_run_witness_package.py`

Requirements:
1. evaluate approved, denied, and policy-rejected scopes without weakening approved or denied invariants;
2. require `proposal_policy_rejected` before terminal run truth;
3. correlate policy-rejection absence checks by `proposal_ref`, or by `(run_id, turn, tool_name, tool_args_hash)` when reading legacy package evidence;
4. require no `proposal_approved`, `tool_invoked`, or `commitment_recorded` for the rejected proposal identity;
5. skip committed-artifact requirements only for scopes whose terminal truth has no committed effect;
6. return stable codes including `policy_rejection_event_missing`, `policy_rejected_proposal_invoked`, `policy_rejected_proposal_committed`, and `full_ledger_export_required`.

Verification:
1. unit: valid policy-rejection package accepts;
2. unit: missing policy-rejection event rejects;
3. unit: tool invocation after policy rejection rejects with `policy_rejected_proposal_invoked`;
4. unit: commitment after policy rejection rejects with `policy_rejected_proposal_committed`;
5. regression: approved and denial base packages still accept.

### Cut 5 - Frozen Policy-Rejection Fixture

Target files:
1. `tests/proof_fixtures/outward_run/base_policy_rejected_package/`
2. `tests/contract/proof/test_outward_run_policy_rejection_package_fixture.py`

Requirements:
1. freeze the verified package emitted by the real policy-rejection proof run;
2. include package-local manifest, bundle, full ledger export, `proposal_ref`, and declared policy authority evidence;
3. exclude committed artifact bytes, approval authority, tool invocation, and commitment evidence;
4. label the fixture real governed-run evidence only if it was captured from the normal outward path.

Verification:
1. contract: frozen policy-rejection fixture verifies offline;
2. contract: fixture contains full ledger export and no committed artifact;
3. contract: fixture rejects if policy authority evidence is removed.

### Cut 6 - Policy-Rejection Corruption Activation

Target files:
1. `scripts/proof/corrupt_outward_run_witness_package.py`
2. `scripts/proof/run_outward_run_corruption_suite.py`
3. `tests/scripts/test_corrupt_outward_run_witness_package.py`
4. `tests/contract/proof/test_outward_run_corruption_suite.py`

Requirements:
1. implement ORP-CORR-031 over `base_policy_rejected_package`;
2. make ORP-CORR-031 reject with `policy_rejected_proposal_invoked`;
3. remove `base_policy_rejected_package_missing` as an accepted blocker after the fixture exists;
4. add a commitment-specific policy-rejection corruption or verifier test that rejects with `policy_rejected_proposal_committed`;
5. keep deterministic mutation bytes for repeated runs.

Verification:
1. contract: ORP-CORR-031 rejects with `policy_rejected_proposal_invoked`;
2. contract: commitment-after-policy-rejection mutation rejects with `policy_rejected_proposal_committed`;
3. contract: corruption suite remains accepted with no policy-rejection missing-fixture blocker;
4. contract: approved and denial corruptions remain green.

### Cut 7 - Assurance Case and Roadmap Closeout Prep

Target files:
1. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/01-assurance-case-index/ASSURANCE_CASE_INDEX_SLICE.md`
2. `scripts/proof/validate_outward_run_assurance_case.py`
3. `benchmarks/results/proof/outward_run_assurance_case_validation.json`
4. `CURRENT_AUTHORITY.md`
5. `docs/ROADMAP.md`
6. `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

Requirements:
1. update ORP-CLAIM-008 from blocker to accepted policy-rejection evidence after live proof succeeds;
2. preserve the out-of-scope blocker until its separate scoped slice is opened;
3. update current authority only for the policy-rejection boundary actually proven;
4. archive only this slice when complete;
5. keep the umbrella extension lane active until remaining families are completed or explicitly retired.

Verification:
1. `python scripts/proof/validate_outward_run_assurance_case.py --output benchmarks/results/proof/outward_run_assurance_case_validation.json`;
2. `python scripts/governance/check_docs_project_hygiene.py`;
3. targeted proof tests for outward package, verifier, invariant, producer, and corruption suite;
4. `git diff --check`.

## Stop Conditions

Stop and report a blocker if:
1. only bundle JSON is available;
2. policy-rejection evidence cannot be captured from normal outward policy handling;
3. the only available rejection is the deferred out-of-scope path;
4. absence is claimed without full `export_scope=all`;
5. a committed artifact or approval authority is required to make policy-rejection verification pass;
6. verifier acceptance needs live runtime state; or
7. public trust wording would need to change.
