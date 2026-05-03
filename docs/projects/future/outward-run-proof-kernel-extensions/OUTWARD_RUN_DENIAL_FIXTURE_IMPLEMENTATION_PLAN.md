# Outward Run Denial Fixture Implementation Plan

Last updated: 2026-05-02
Status: Active implementation lane
Owner: Orket Core

Accepted requirements: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_DENIAL_FIXTURE_REQUIREMENTS_V1.md`
Base closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/`

## Purpose

Extend the completed approved single-turn proof kernel with one denial-path package family:

```text
outward_run_write_file_denied_v1
```

The lane closes only when a real governed outward denial package verifies offline and the denial corruption path is falsifiable.

## Non-Goals

This lane does not cover policy rejection, out-of-scope proposal rejection, multi-turn proof, ODR determinism, public trust wording, or claim posture above `outward_lab_only`.

## Implementation Rules

1. Accepted denial proof requires `--package`; bundle-only JSON remains introspection-only.
2. The offline verifier may read only package-local `manifest.json`, `outward_witness_bundle.json`, `ledger_export.json`, and declared package-local evidence.
3. Denial packages must not fabricate committed artifact bytes.
4. Absence claims require full `ledger_export.v1` bytes with `export_scope=all`.
5. Existing approved-path verification and corruption behavior must remain green.

## Cuts

### Cut 1 - Contract Delta

Target files:
1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`

Requirements:
1. admit `outward_run_write_file_denied_v1`;
2. define denial package artifact rules with no `committed_output`;
3. activate ORP-INV-013 and ORP-INV-022 for denial;
4. keep denial single-package posture capped at `outward_lab_only`.

Verification:
1. `python scripts/governance/check_docs_project_hygiene.py`;
2. `git diff --check`.

### Cut 2 - Package Builder and Loader Support

Target files:
1. `scripts/proof/outward_run_witness_contract.py`
2. `scripts/proof/outward_run_witness_package.py`
3. `scripts/proof/outward_run_witness_builder.py`
4. `scripts/proof/emit_outward_run_witness_package.py`
5. `tests/scripts/test_emit_outward_run_witness_package.py`
6. `tests/scripts/test_outward_run_witness_package.py`

Requirements:
1. support `outward_run_write_file_denied_v1` as an admitted compare scope;
2. emit a package with full ledger export and model/approval/run authority evidence;
3. omit committed artifact refs for denial packages;
4. fail closed if a denied package has tool result state or committed artifact refs for the denied approval id.

Verification:
1. unit: loader accepts minimal denial package without artifact refs;
2. contract: producer emits denial package layout from a seeded denied run;
3. contract: producer rejects denial packages with effect artifacts.

### Cut 3 - Verifier and Invariant Checker

Target files:
1. `scripts/proof/outward_run_invariant_checker.py`
2. `scripts/proof/verify_outward_run_witness_package.py`
3. `tests/scripts/test_outward_run_invariant_checker.py`
4. `tests/scripts/test_verify_outward_run_witness_package.py`

Requirements:
1. evaluate approved and denied scopes without weakening approved-path invariants;
2. require `proposal_denied` before terminal run truth;
3. require no `tool_invoked` and no `commitment_recorded` for the denied approval id;
4. skip approved-path committed-artifact requirements only for denial scope;
5. return stable codes including `denial_event_missing`, `denied_proposal_invoked`, and `full_ledger_export_required`.

Verification:
1. unit: valid denial package accepts;
2. unit: missing denial event rejects;
3. unit: tool invocation after denial rejects with `denied_proposal_invoked`;
4. regression: approved base package still accepts.

### Cut 4 - Real Denial Fixture Capture

Target files:
1. `scripts/proof/run_outward_write_file_denied_proof.py`
2. `tests/proof_fixtures/outward_run/base_denied_package/`
3. `tests/contract/proof/test_outward_run_denial_package_fixture.py`

Requirements:
1. originate the run from normal outward submission;
2. deny through the normal approval service or API path;
3. set `ORKET_DISABLE_SANDBOX=1` for routine proof execution;
4. emit the denial witness package;
5. verify the package offline before freezing the fixture;
6. record any environment blocker truthfully.

Verification:
1. integration: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_denied_proof.py`;
2. contract: frozen denial fixture verifies offline;
3. contract: fixture contains manifest, bundle, and full ledger export, and no committed artifact.

### Cut 5 - Denial Corruption Activation

Target files:
1. `scripts/proof/corrupt_outward_run_witness_package.py`
2. `scripts/proof/run_outward_run_corruption_suite.py`
3. `tests/scripts/test_corrupt_outward_run_witness_package.py`
4. `tests/contract/proof/test_outward_run_corruption_suite.py`

Requirements:
1. implement ORP-CORR-030 over `base_denied_package`;
2. implement the denial side of ORP-CORR-068 if it can use the denial fixture without policy fixture drift;
3. keep policy-rejection and out-of-scope corruptions explicitly blocked;
4. keep deterministic mutation bytes for repeated runs.

Verification:
1. contract: ORP-CORR-030 rejects with `denied_proposal_invoked`;
2. contract: denial partial-export corruption rejects with `full_ledger_export_required` if implemented;
3. contract: approved-path corruption suite remains accepted;
4. contract: remaining missing fixtures remain explicit blockers.

### Cut 6 - Assurance Case and Roadmap Closeout Prep

Target files:
1. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/01-assurance-case-index/ASSURANCE_CASE_INDEX_SLICE.md`
2. `scripts/proof/validate_outward_run_assurance_case.py`
3. `benchmarks/results/proof/outward_run_assurance_case_validation.json`
4. `CURRENT_AUTHORITY.md`
5. `docs/ROADMAP.md`

Requirements:
1. update ORP-CLAIM-007 from blocker to accepted denial evidence after live proof succeeds;
2. preserve blockers for policy-rejection and out-of-scope rows;
3. update current authority only for the denial boundary actually proven;
4. do not archive this active lane until verification artifacts, specs, roadmap, and authority agree.

Verification:
1. `python scripts/proof/validate_outward_run_assurance_case.py --output benchmarks/results/proof/outward_run_assurance_case_validation.json`;
2. `python scripts/governance/check_docs_project_hygiene.py`;
3. targeted proof tests for outward package, verifier, invariant, producer, and corruption suite;
4. `git diff --check`.

## Stop Conditions

Stop and report a blocker if:
1. only bundle JSON is available;
2. denial evidence cannot be captured from normal outward approval denial;
3. absence is claimed without full `export_scope=all`;
4. a committed artifact is required to make denial verification pass;
5. verifier acceptance needs live runtime state; or
6. public trust wording would need to change.
