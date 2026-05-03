# Outward Run Proof Kernel Implementation Plan

Last updated: 2026-05-02
Status: Closed for approved single-turn proof kernel - path-family extensions deferred with blockers
Owner: Orket Core

Accepted requirements: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_REQUIREMENTS_V1.md`
Closeout record: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/CLOSEOUT.md`
Future extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

Primary authority dependencies:
1. `CURRENT_AUTHORITY.md`
2. `docs/ARCHITECTURE.md`
3. `docs/specs/ORKET_OPERATING_PRINCIPLES.md`
4. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
5. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
6. `docs/specs/FINITE_TRUST_KERNEL_MODEL_V1.md`
7. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
8. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
9. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
10. `docs/specs/LEDGER_EXPORT_V1.md`

Specs promoted by this closeout:
1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` - active for the approved single-turn boundary
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md` - active for the approved single-turn boundary
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md` - active for outward proof posture assignment
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md` - active for assurance-case validation

Archived slice planning docs for the completed boundary:
1. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/01-assurance-case-index/ASSURANCE_CASE_INDEX_SLICE.md`
2. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/02-outward-run-witness-bundle/OUTWARD_RUN_WITNESS_BUNDLE_SLICE.md`
3. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/03-invariant-checker/INVARIANT_CHECKER_SLICE.md`
4. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/04-negative-corruption-suite/NEGATIVE_CORRUPTION_SUITE_SLICE.md`
5. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/05-non-fixture-useful-slice/NON_FIXTURE_USEFUL_SLICE.md`
6. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/06-claim-tier-taxonomy/CLAIM_TIER_TAXONOMY_SLICE.md`

Moved future slice planning docs:
1. `docs/projects/future/outward-run-proof-kernel-extensions/07-multi-turn-sequence-proof/MULTI_TURN_SEQUENCE_PROOF_SLICE.md`
2. `docs/projects/future/outward-run-proof-kernel-extensions/08-odr-determinism-integration/ODR_DETERMINISM_INTEGRATION_SLICE.md`

Supporting planning note:
1. `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/STATE_MACHINE_FORMALISM_NOTE.md`

## Purpose

Make the completed outward-facing run pipeline independently checkable as a bounded proof surface.

This lane starts from the shipped outward pipeline checkpoint and adds the proof kernel needed to answer:
1. what claim is being made,
2. which invariant ids support it,
3. which serialized evidence carries authority,
4. which verifier command accepts or rejects it, and
5. which claim posture the evidence permits.

## Current Authority Context

As of this lane activation:
1. the outward-facing pipeline checkpoint is closed and archived under `docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/`;
2. active runtime/operator authority for the outward pipeline remains in `CURRENT_AUTHORITY.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/RUNBOOK.md`, `docs/SECURITY.md`, and `docs/specs/LEDGER_EXPORT_V1.md`;
3. the current externally admitted public trust slice remains `trusted_repo_config_change_v1`;
4. the active trust contract forbids broad claims that the whole runtime is mathematically proven; and
5. this lane may prepare a broader trust boundary only when evidence and same-change authority updates support it.

## Governing Decisions

1. The lane extends the current trusted-run, finite-model, invariant, substrate, and determinism vocabulary.
2. New authority nouns are allowed only when they answer a verifier question.
3. Proof evaluation consumes serialized evidence only.
4. Projection-only surfaces remain support-only unless a durable contract explicitly upgrades their role with preserved source authority.
5. Control Plane work is in scope only where it supplies required evidence or authority refs.
6. Data Plane work is in scope only where it supplies proof-bearing effect evidence.
7. Public trust wording remains bounded by `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` until proof and same-change contract updates support a wider boundary.
8. Slices 07 and 08 are deferred extensions; they must not block the single-turn proof kernel.

## Concrete Implementation Plan

This section is the execution order for Workstreams 1 through 6. It is intentionally package-first: implementation must not build a successful proof path around `outward_witness_bundle.json` alone.

Hard implementation rules:
1. Do not implement any accepted proof path from `outward_witness_bundle.json` alone. Accepted proof claims require `--package` and package-local `manifest.json`, `outward_witness_bundle.json`, `ledger_export.json`, and artifact bytes.
2. The package producer may read persisted outward runtime records to build finite evidence. The offline verifier may not read persisted runtime records, live databases, APIs, providers, clocks, environment-derived policy, network services, or mutable workspace paths outside the package.

### Cut 1 - Package Contract Kernel

Goal: create the side-effect-free package loader and report primitives before any producer or live fixture exists.

Target files:
1. `scripts/proof/outward_run_witness_package.py`
2. `scripts/proof/outward_run_witness_contract.py`
3. `tests/scripts/test_outward_run_witness_package.py`

Implementation requirements:
1. load `outward_run_witness_package.v1/manifest.json`, `outward_witness_bundle.json`, `ledger_export.json`, and declared artifact files from a package directory;
2. reject any package ref that resolves outside the package root using `Path.resolve()` plus `Path.is_relative_to()`;
3. recompute manifest file digests from package bytes;
4. expose package-level failure codes: `package_manifest_missing`, `package_manifest_digest_mismatch`, `bundle_missing`, and `package_ref_outside_package`;
5. keep bundle-only loading schema/introspection-only and unable to produce `accepted` proof claims.

Verification:
1. unit: package loader accepts a minimal valid package fixture under `tmp_path`;
2. unit: missing manifest, missing bundle, digest drift, and path escape fail closed with stable codes;
3. unit: bundle-only mode cannot return an accepted proof result.

### Cut 2 - Offline Verifier Skeleton and Report Writer

Goal: establish the verifier command and output contract early, even before every invariant is implemented.

Target files:
1. `scripts/proof/verify_outward_run_witness_package.py`
2. `scripts/proof/outward_run_witness_report.py`
3. `tests/scripts/test_verify_outward_run_witness_package.py`
4. optional compatibility alias: `scripts/proof/verify_outward_run_witness_bundle.py`

Implementation requirements:
1. accept `--package`, `--scope`, and `--output`;
2. reject proof execution without `--package`;
3. never open outward stores, runtime databases, APIs, network services, providers, clocks for ordering, process environment for policy, or mutable workspace paths outside the package;
4. write rerunnable JSON results with `scripts.common.rerun_diff_ledger.write_payload_with_diff_ledger`;
5. return `rejected` or `downgraded` rather than success-shaped output for unsupported evidence.
6. if the compatibility alias exists, it must preserve package-only proof acceptance; bundle-only use remains schema/introspection-only.

Verification:
1. contract: command rejects missing package with stable output;
2. contract: command writes `outward_run_witness_report.v1`;
3. unit: output is deterministic for identical package bytes.

### Cut 3 - Ledger and Artifact Verification

Goal: make package authority real before higher-level invariants depend on it.

Target files:
1. `scripts/proof/outward_run_witness_ledger.py`
2. `scripts/proof/validate_outward_write_file_committed.py`
3. `tests/scripts/test_outward_run_witness_ledger.py`
4. `tests/scripts/test_validate_outward_write_file_committed.py`

Implementation requirements:
1. verify packaged `ledger_export.json` using `docs/specs/LEDGER_EXPORT_V1.md` semantics and existing pure `verify_ledger_export` support;
2. require full `export_scope=all` for completeness and absence claims;
3. reject missing payload bytes needed to recompute event hashes;
4. verify `artifact_refs[committed_output]` against `artifacts/committed_output`;
5. keep digest-only summaries support-only unless source bytes are included or anchored by the verified ledger export.

Verification:
1. contract: missing `ledger_export.json` returns `ledger_export_missing`;
2. contract: changed export bytes return `ledger_export_digest_mismatch` or `ledger_chain_hash_mismatch` as applicable;
3. contract: missing or changed committed artifact bytes return `committed_artifact_missing` or `artifact_digest_mismatch`;
4. integration: keep existing outward ledger behavior green with `python -m pytest -q tests/application/test_outward_ledger_service.py`.

### Cut 4 - Invariant Checker

Goal: mechanize ORP-INV-001 through ORP-INV-014, ORP-INV-016, and ORP-INV-022 for the single-turn scope.

Target files:
1. `scripts/proof/outward_run_invariant_checker.py`
2. `tests/scripts/test_outward_run_invariant_checker.py`

Implementation requirements:
1. compute the canonical approved sequence from the packaged full ledger export;
2. enforce no effect before admission and no approval-required effect before approval;
3. enforce final-truth alignment across `run_authority.status`, `run_authority.run_status`, exactly one terminal ledger event, and commitment state;
4. enforce effect evidence, approval/effect tool digest alignment, commitment after effect, turn completion after commitment, and strict ledger ordering;
5. enforce ORP-INV-012 by matching model invocation, prompt, response, and proposal-extraction digests from the `proposal_made` payload to `model_invocation_evidence`;
6. enforce denial, policy-rejection, and absence claims only with full `export_scope=all`;
7. produce a stable invariant signature that excludes timestamps, generated ids, paths, and model text content.

Verification:
1. unit: every single-turn invariant has at least one passing and one failing focused case where practical;
2. contract: failure codes match `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`;
3. contract: equivalent successful package fixtures produce the same invariant signature.

### Cut 5 - Witness Package Producer

Goal: emit a finite package from real outward-run persisted evidence.

Target files:
1. `scripts/proof/emit_outward_run_witness_package.py`
2. `scripts/proof/outward_run_witness_builder.py`
3. `tests/scripts/test_emit_outward_run_witness_package.py`

Implementation requirements:
1. read persisted outward run, approval, event, ledger export, model evidence, and committed artifact bytes for a supplied `--run-id`;
2. call outward ledger export with full `types=all` semantics for the initial proof kernel;
3. copy committed artifact bytes into `artifacts/committed_output`;
4. write `manifest.json`, `outward_witness_bundle.json`, `ledger_export.json`, and artifacts under one package directory;
5. avoid live providers, network calls, clocks for ordering, or runtime state outside the source persisted records while building the package;
6. fail closed if required source bytes or verified ledger anchors are missing.

Verification:
1. contract: producer emits the exact package layout from a seeded outward-run database and workspace under `tmp_path`;
2. integration: producer output verifies with the offline package verifier;
3. integration: existing outward execution remains green with `python -m pytest -q tests/application/test_outward_run_execution_service.py`.

### Cut 6 - Real Package Fixture Capture

Goal: create the first non-hand-authored base package for corruption development.

Target files:
1. `tests/proof_fixtures/outward_run/base_approved_package/`
2. `scripts/proof/capture_outward_write_file_approved_package.py`
3. `tests/contract/proof/test_outward_run_witness_package_fixture.py`

Implementation requirements:
1. originate the run from the normal outward operator path, preferably `POST /v1/runs` plus the existing approval path;
2. use `ORKET_DISABLE_SANDBOX=1` unless the flow intentionally proves sandbox setup and teardown;
3. approve the generated `write_file` proposal through the normal approval surface or service path used by the API;
4. emit a package from that run with `emit_outward_run_witness_package.py`;
5. verify the package and committed artifact before freezing it as `base_approved_package/`;
6. clearly label any synthetic development fixture as synthetic and ineligible for lane closeout.

Verification:
1. contract: fixture package verifies offline;
2. contract: fixture contains full `ledger_export.json`, manifest, bundle, and `artifacts/committed_output`;
3. integration: the capture command records observed path/result as `primary`/`success` or a truthful blocker.

### Cut 7 - Negative Corruption Suite

Goal: prove the checker is falsifiable over packages, not bundle-only JSON.

Target files:
1. `scripts/proof/corrupt_outward_run_witness_package.py`
2. `scripts/proof/run_outward_run_corruption_suite.py`
3. `tests/scripts/test_corrupt_outward_run_witness_package.py`
4. `tests/contract/proof/test_outward_run_corruption_suite.py`

Implementation requirements:
1. implement ORP-CORR-001 through ORP-CORR-082 for the approved base package, with denial/policy cases blocked until their package fixtures exist;
2. mutate manifest, bundle, full ledger export, committed artifact bytes, claim tier requests, and invariant-specific evidence;
3. keep deterministic seed behavior for any generated mutation choices;
4. write rerunnable suite JSON with the diff-ledger writer;
5. require each corruption to produce the exact expected failure code from Slice 04.

Verification:
1. contract: approved base package is accepted before corruption;
2. contract: every implemented ORP-CORR id rejects with the expected code;
3. contract: unimplemented path-family ids report explicit missing-fixture blockers rather than disappearing.

### Cut 8 - Claim Tier Enforcement and Campaign Stability

Goal: make claim posture assignment mechanical.

Target files:
1. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`
2. `scripts/proof/outward_run_claim_tiers.py`
3. `scripts/proof/run_outward_run_witness_campaign.py`
4. `tests/scripts/test_outward_run_claim_tiers.py`
5. `tests/scripts/test_run_outward_run_witness_campaign.py`

Implementation requirements:
1. implement `outward_lab_only`, `outward_verifier_stable`, `outward_externally_checkable`, and `outward_public_trust` ceilings;
2. compute the strongest evidence-supported ceiling, then assign no claim above the requested posture or the evidence-supported ceiling;
3. reject requests above the evidence-supported ceiling with `claim_tier_not_supported`;
4. assign `outward_verifier_stable` only from multiple accepted verifier reports with matching invariant signatures.

Verification:
1. unit: each posture has positive and negative ceiling tests;
2. contract: one accepted package cannot claim `outward_verifier_stable`;
3. contract: matching accepted reports can produce a campaign report with stable invariant signature.

### Cut 9 - Non-Fixture Useful Proof Chain

Goal: run the selected useful scope end to end and publish only the proof boundary that was actually achieved.

Target files:
1. `scripts/proof/run_outward_write_file_approved_proof.py`
2. `benchmarks/results/proof/outward_run_witness_report.json`
3. `benchmarks/results/proof/outward_write_file_validation.json`
4. `benchmarks/results/proof/outward_run_corruption_report.json`

Implementation requirements:
1. drive the normal outward run path for `outward_run_write_file_approved_v1`;
2. emit the witness package;
3. validate committed artifact bytes from the package;
4. verify invariants offline from `--package`;
5. run the approved-path corruption suite;
6. update the assurance case index with exact artifact paths and blocker status.

Verification:
1. integration: `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_approved_proof.py`;
2. contract: rerun verifier directly with `python scripts/proof/verify_outward_run_witness_package.py --package <package> --scope outward_run_write_file_approved_v1 --output benchmarks/results/proof/outward_run_witness_report.json`;
3. contract: rerun committed-artifact validator directly;
4. contract: rerun corruption suite directly.

### Cut 9.5 - Assurance Case Schema Extraction

Goal: prevent the assurance case index from becoming prose-only after proof artifacts exist.

Target files:
1. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`
2. `scripts/proof/validate_outward_run_assurance_case.py`
3. `tests/scripts/test_validate_outward_run_assurance_case.py`

Implementation requirements:
1. define the machine-readable claim row shape for claim id, compare scope, operator surface, invariant ids, authority evidence refs, verifier command, claim posture, and blocker status;
2. validate the Slice 01 assurance case index against that shape or against an extracted machine-readable representation;
3. fail closed when a claim row lacks authority evidence, uses support-only evidence as authority, omits invariant ids, or points to a verifier command that cannot consume `--package`;
4. keep public trust wording out of the assurance case schema.

Verification:
1. contract: valid initial assurance case rows pass validation;
2. contract: missing authority refs, missing invariant ids, support-only authority substitution, and bundle-only verifier commands fail with stable reason codes.

### Cut 10 - Spec Promotion and Lane Closeout

Goal: promote only the contracts proven by code and leave future extensions deferred.

Target files:
1. `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
2. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`
3. `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md`
4. `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md`
5. `CURRENT_AUTHORITY.md`
6. `docs/ROADMAP.md`

Implementation requirements:
1. change draft specs to active durable contracts only after package producer, verifier, invariant checker, assurance-case validator, and corruption suite are green;
2. record exact accepted commands and output paths in `CURRENT_AUTHORITY.md`;
3. keep public trust wording unchanged unless `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md` is updated in the same change with matching evidence;
4. archive the lane only after the roadmap, authority snapshot, specs, evidence artifacts, and tests agree.

Verification:
1. docs hygiene: `python scripts/governance/check_docs_project_hygiene.py`;
2. targeted test suite for all new proof scripts;
3. final proof command chain from Cut 9;
4. `git diff --check`.

## Implementation Stop Conditions

Stop and report a truthful blocker instead of proceeding if:
1. the only available evidence is bundle JSON without a full package;
2. a digest is needed as authority but source bytes or a verified ledger anchor are missing;
3. absence is claimed without a full `ledger_export.v1` with `export_scope=all`;
4. the proposed fixture is hand-authored, synthetic, or bypasses the normal outward run path;
5. the verifier needs a live database, clock, provider, API, environment-derived policy, network service, or mutable workspace path outside the package;
6. a new proof script would write JSON without the repository diff-ledger writer;
7. public trust wording would need to change before the evidence supports it.

## Workstream 0 - Lane Activation

### Status

Complete for lane activation. Slice detail was expanded after activation.

### Exit Criteria Met

1. `docs/ROADMAP.md` points `Priority Now` at this implementation plan.
2. the project folder appears in the Project Index.
3. docs project hygiene passed at activation.

## Workstream 1 - Assurance Case Index

### Goal

Create one canonical map from claim to invariant ids, evidence artifacts, verifier commands, and claim posture.

### Current State

Slice 01 contains a 10-row draft assurance case index for `outward_run_write_file_approved_v1` and related denial, policy-rejection, out-of-scope, and campaign paths.

### Tasks

1. ratify or revise the 10-claim draft in Slice 01
2. classify each artifact as authority, claim, derived, support-only, or forbidden substitute
3. add a machine-readable validation command once the index format stabilizes
4. extract the index schema to `docs/specs/OUTWARD_RUN_ASSURANCE_CASE_SCHEMA_V1.md` before scripts depend on it

### Exit Criteria

1. every initial outward-run proof claim has a compare scope, operator surface, claim posture, evidence refs, invariant ids, and verifier path
2. support-only materials cannot masquerade as proof authority
3. unresolved blockers are explicit

## Workstream 2 - Outward Run Witness Package

### Goal

Define and emit a portable outward-run witness package for the v1 outward pipeline.

### Current State

Slice 02 contains a full package and bundle contract draft. `docs/specs/OUTWARD_RUN_WITNESS_V1.md` is staged as a draft spec and is not yet durable authority.

### Tasks

1. ratify the package and bundle contract draft in Slice 02
2. implement `scripts/proof/emit_outward_run_witness_package.py` for `outward_run_write_file_approved_v1`
3. implement `scripts/proof/verify_outward_run_witness_package.py` as an offline verifier over package bytes with `--package` as the only proof-accepting input; keep `scripts/proof/verify_outward_run_witness_bundle.py` only as a compatibility alias if needed
4. extract the accepted package contract to `docs/specs/OUTWARD_RUN_WITNESS_V1.md`
5. keep multi-turn and ODR sections optional until Slices 07 and 08 are active implementation work

### Exit Criteria

1. an outward run can emit a witness package containing bundle JSON, full ledger export JSON, package manifest, and committed artifact bytes
2. the package can be loaded and checked without live databases, clocks, providers, network, mutable runtime state, or mutable workspace paths outside the package
3. digest-only commitments without source bytes or verified ledger anchors produce blockers instead of success-shaped verifier output

## Workstream 3 - Invariant Checker

### Goal

Mechanize the outward-run invariant model.

### Current State

Slice 03 drafts ORP-INV-001 through ORP-INV-022. `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md` is staged as a draft spec and is not yet durable authority.

### Tasks

1. ratify the ORP-INV table in Slice 03
2. implement the checker as a side-effect-free function over package bytes
3. link checker code blocks to the state-machine transitions in `STATE_MACHINE_FORMALISM_NOTE.md` where practical
4. add focused property-based tests if `hypothesis` is already available or can be added without dependency drift
5. produce a stable invariant signature for campaign comparison
6. extract the accepted invariant table to `docs/specs/OUTWARD_RUN_INVARIANTS_V1.md`

### Exit Criteria

1. the checker accepts a valid outward-run witness package for the admitted single-turn compare scope
2. the checker fails closed on missing or contradictory evidence
3. the invariant signature is stable for equivalent successful evidence

## Workstream 4 - Negative Corruption Suite

### Goal

Make the proof falsifiable through stable fail-closed corruption coverage.

### Current State

Slice 04 contains a package-level corruption matrix with ids reserved through ORP-CORR-094. Single-turn corruptions are part of the first closeout gate. Multi-turn corruptions are reserved for Slice 07.

### Immediate Blocker

Create this fixture from a real governed-run v1 witness package:

```text
tests/proof_fixtures/outward_run/base_approved_package/
```

### Tasks

1. create `tests/proof_fixtures/outward_run/base_approved_package/` from a real governed-run witness package
2. implement `scripts/proof/corrupt_outward_run_witness_package.py` with deterministic per-id package mutations
3. run each active ORP-CORR corruption and confirm expected failure codes
4. create denial and policy-rejection fixtures after the approval path is green
5. add negative proof artifact paths to the assurance case index

### Exit Criteria

1. each admitted single-turn invariant has at least one positive or negative proof path
2. must-catch package, ledger, artifact, invariant, and claim-tier corruptions fail with stable reason codes
3. negative proof artifacts are included in the assurance case index

## Workstream 5 - Non-Fixture Useful Slice

### Goal

Promote one externally useful non-fixture outward workflow scope into the proof kernel.

### Current State

Slice 05 selects `outward_run_write_file_approved_v1`.

### Tasks

1. implement the three-step positive proof chain: emit witness package, validate committed artifact from the package, verify invariants
2. run on a real outward run
3. run negative corruption proof
4. update the assurance case index

### Exit Criteria

1. one non-fixture outward workflow has a complete proof package or truthful blocker
2. the offline verifier assigns only the posture supported by evidence
3. public wording remains unchanged unless the trust contract is updated truthfully in the same change

## Workstream 6 - Claim Tier Taxonomy

### Goal

Define and extract the outward claim posture ladder so the invariant checker can enforce ceilings mechanically.

### Current State

Slice 06 drafts four lane-local outward postures: `outward_lab_only`, `outward_verifier_stable`, `outward_externally_checkable`, and `outward_public_trust`.

### Tasks

1. ratify the ladder in Slice 06
2. implement ceiling enforcement in the invariant checker
3. extract to `docs/specs/OUTWARD_RUN_CLAIM_TIERS_V1.md` before scripts or public wording depend on it
4. reconcile any determinism wording with `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`

### Exit Criteria

1. four postures are defined with minimum evidence requirements
2. checker enforces ceilings without manual override
3. the ladder is extracted before public wording references it

## Workstream 7 - Multi-Turn Sequence Proof

### Status

Deferred extension.

### Goal

Extend the proof kernel to `governed_tool_sequence` multi-turn runs.

### Precondition

Workstreams 1 through 6 must close or remain green before this workstream can close.

### Current State

Slice 07 drafts ORP-INV-015 through ORP-INV-020 and ORP-CORR-090 through ORP-CORR-094.

## Workstream 8 - ODR Determinism Integration

### Status

Deferred extension.

### Goal

Connect bounded ODR canonicalization evidence to a future outward deterministic posture without claiming model text determinism or whole-run determinism.

### Precondition

Workstreams 1 through 6 must close or remain green before this workstream can close.

### Current State

Slice 08 drafts ORP-INV-021 and an optional `odr_evidence` bundle extension.

## Strategic Completion Gate

This lane can close only when all of the following are true:
1. the assurance case index is complete for the admitted outward proof scope,
2. the outward witness package exists and verifies offline,
3. invariant checking is mechanized with stable reason codes,
4. the negative corruption suite proves falsifiability for the single-turn scope,
5. one externally useful non-fixture scope has been selected and proven or truthfully blocked,
6. the claim posture taxonomy is extracted as durable authority, and
7. roadmap, current authority, and durable specs do not contradict the actual proof boundary.

Workstreams 7 and 8 are useful extensions but are not required for the initial single-turn proof-kernel closeout.

## Closeout Evidence

Closed boundary: `outward_run_write_file_approved_v1` approved single-turn package proof.

Accepted proof commands:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_outward_write_file_approved_proof.py`
2. `python scripts/proof/verify_outward_run_witness_package.py --package benchmarks/results/proof/outward_run_witness_package.v1 --scope outward_run_write_file_approved_v1 --output benchmarks/results/proof/outward_run_witness_report.json`
3. `python scripts/proof/validate_outward_write_file_committed.py --package benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_write_file_validation.json`
4. `python scripts/proof/run_outward_run_corruption_suite.py --base benchmarks/results/proof/outward_run_witness_package.v1 --output benchmarks/results/proof/outward_run_corruption_report.json`
5. `python scripts/proof/validate_outward_run_assurance_case.py --output benchmarks/results/proof/outward_run_assurance_case_validation.json`

Accepted proof artifacts:
1. `benchmarks/results/proof/outward_run_witness_package.v1/`
2. `benchmarks/results/proof/outward_run_witness_report.json`
3. `benchmarks/results/proof/outward_write_file_validation.json`
4. `benchmarks/results/proof/outward_run_corruption_report.json`
5. `benchmarks/results/proof/outward_run_assurance_case_validation.json`
6. `tests/proof_fixtures/outward_run/base_approved_package/`

Deferred blockers:
1. denial fixture package: `base_denied_package_missing`
2. policy-rejection fixture package: `base_policy_rejected_package_missing`
3. out-of-scope path-family package: blocked until policy-rejection package exists

Public trust wording remains unchanged.
