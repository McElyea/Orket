# Slice 04 - Negative Corruption Suite

Last updated: 2026-05-01
Status: Archived slice plan - approved-path corruptions implemented; denial and policy-rejection corruptions updated by later slice closeouts
Owner: Orket Core

Parent closeout: `docs/projects/archive/outward-run-proof-kernel/2026-05-02-OUTWARD-RUN-PROOF-KERNEL-CLOSEOUT/OUTWARD_RUN_PROOF_KERNEL_IMPLEMENTATION_PLAN.md`
Future extensions: `docs/projects/future/outward-run-proof-kernel-extensions/OUTWARD_RUN_PROOF_KERNEL_EXTENSIONS.md`

## Purpose

Make outward-run proof falsifiable by mutating serialized evidence and requiring stable fail-closed reason codes.

## Guiding Principle

A proof that can only succeed is not a proof. Each must-catch corruption in this suite is a falsifiability test. The suite passes only when:
1. the valid base witness package is accepted, and
2. each corrupted witness package is rejected with the expected failure code.

## Base Package Convention

The corruption suite operates against one canonical base witness package directory per admitted path:

| Fixture | Meaning |
|---|---|
| `tests/proof_fixtures/outward_run/base_approved_package/` | single-turn approval path |
| `tests/proof_fixtures/outward_run/base_denied_package/` | denial path |
| `tests/proof_fixtures/outward_run/base_policy_rejected_package/` | policy rejection path |
| `tests/proof_fixtures/outward_run/base_multi_turn_approved_package/` | deferred multi-turn path |

Approved-path base packages must contain:

```text
manifest.json
outward_witness_bundle.json
ledger_export.json
artifacts/
  committed_output
```

Denial-path and policy-rejection packages intentionally omit committed artifact bytes because no connector effect occurred. Each base package must be a valid `outward_run_witness_package.v1` for its compare scope that the verifier accepts before corruption is applied. Bundle-only fixtures are invalid for this suite because they cannot prove full ledger integrity, absence of omitted events, or committed artifact bytes where a committed effect is claimed.

## Corruption Helper Target

```bash
python scripts/proof/corrupt_outward_run_witness_package.py \
  --base tests/proof_fixtures/outward_run/base_approved_package \
  --corruption-id ORP-CORR-001 \
  --output /tmp/corrupted_package
```

The helper must be deterministic: the same `--base` and `--corruption-id` must produce the same bytes.
The helper mutates package files, not only `outward_witness_bundle.json`. The verifier input is `--package` only; any bundle-only verifier mode is limited to schema or introspection checks and cannot return `accepted` for proof claims.

## Corruption Matrix - v1 Draft

The matrix reserves ids through `ORP-CORR-094`. Gaps are intentional and leave room for adjacent corruptions without renumbering accepted ids.

### Schema and Scope Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-001 | base_approved | remove `schema_version` | `bundle_schema_missing_or_unsupported` | schema gate |
| ORP-CORR-002 | base_approved | change `schema_version` to `outward_run.witness_bundle.v0` | `bundle_schema_missing_or_unsupported` | schema gate |
| ORP-CORR-003 | base_approved | change `compare_scope` to `unknown_scope` | `compare_scope_missing_or_unsupported` | schema gate |
| ORP-CORR-004 | base_approved | change `operator_surface` to an unsupported value | `operator_surface_missing` | schema gate |
| ORP-CORR-005 | base_approved | remove `manifest.json` | `package_manifest_missing` | package gate |
| ORP-CORR-006 | base_approved | change a package file without updating `manifest.json` digest material | `package_manifest_digest_mismatch` | package gate |
| ORP-CORR-007 | base_approved | remove `outward_witness_bundle.json` | `bundle_missing` | package gate |
| ORP-CORR-008 | base_approved | set a `package_refs` path to escape the package root | `package_ref_outside_package` | package gate |
| ORP-CORR-009 | base_approved | point `artifact_refs[committed_output]` outside the package | `package_ref_outside_package` | package gate |

### Admission and Ordering Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-010 | base_approved | remove `run_submitted` event | `effect_before_admission` | ORP-INV-001 |
| ORP-CORR-011 | base_approved | move `run_submitted` after `tool_invoked` | `effect_before_admission` | ORP-INV-001 |
| ORP-CORR-012 | base_approved | remove `run_authority` block | `run_authority_missing` | schema gate |
| ORP-CORR-013 | base_approved | change `run_authority.run_id` to a different id | `run_id_drift` | ORP-INV-001 |

### Approval Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-020 | base_approved | remove `proposal_approved` event | `effect_before_approval` | ORP-INV-002 |
| ORP-CORR-021 | base_approved | move `proposal_approved` after `tool_invoked` | `effect_before_approval` | ORP-INV-002 |
| ORP-CORR-022 | base_approved | remove `approval_authority` list | `approval_authority_missing` | ORP-INV-002 |
| ORP-CORR-023 | base_approved | set approval authority status to `denied` | `approval_status_not_approved` | ORP-INV-002 |
| ORP-CORR-024 | base_approved | change approval `tool_args_digest` | `tool_args_digest_drift` | ORP-INV-009 |
| ORP-CORR-025 | base_approved | change effect `tool_args_digest` | `tool_args_digest_drift` | ORP-INV-009 |
| ORP-CORR-026 | base_approved | change approved tool name | `tool_args_digest_drift` | ORP-INV-009 |

### Denial and Policy Rejection Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-030 | base_denied | add synthetic `tool_invoked` after `proposal_denied` for the same approval id | `denied_proposal_invoked` | ORP-INV-013 |
| ORP-CORR-031 | base_policy_rejected | add synthetic `tool_invoked` after `proposal_policy_rejected` for the same `proposal_ref` | `policy_rejected_proposal_invoked` | ORP-INV-014 |

### Effect and Commitment Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-040 | base_approved | remove `tool_invoked` event | `effect_evidence_missing` | ORP-INV-004 |
| ORP-CORR-041 | base_approved | remove `effect_evidence` list | `effect_evidence_missing` | ORP-INV-004 |
| ORP-CORR-042 | base_approved | remove `commitment_recorded` event | `commitment_missing_after_effect` | ORP-INV-010 |
| ORP-CORR-043 | base_approved | remove `turn_completed` event | `turn_not_completed_after_commitment` | ORP-INV-011 |

### Final Truth Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-050 | base_approved | remove `run_completed` event | `final_truth_missing` | ORP-INV-003 |
| ORP-CORR-051 | base_approved | change all terminal success statuses to failure | `final_truth_missing` | ORP-INV-003 |
| ORP-CORR-052 | base_approved | duplicate `run_completed` event | `terminal_status_drift` | ORP-INV-003 |
| ORP-CORR-053 | base_approved | set `run_authority.status` to success while ledger terminal event is failure | `terminal_status_drift` | ORP-INV-003 |
| ORP-CORR-054 | base_approved | set ledger terminal event to success while `run_authority.run_status` is failure | `terminal_status_drift` | ORP-INV-003 |
| ORP-CORR-055 | base_approved | keep `tool_invoked` and success terminal truth but remove matching `commitment_recorded` | `commitment_missing_after_effect` | ORP-INV-003 |
| ORP-CORR-056 | base_approved | change `commitment_recorded` to a wrong `approval_id` or `turn_index` | `commitment_missing_after_effect` | ORP-INV-003 |

### Ledger Integrity Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-060 | base_approved | change an event `previous_chain_hash` to an incorrect value | `ledger_chain_broken` | ORP-INV-006 |
| ORP-CORR-061 | base_approved | change `ledger_evidence.ledger_hash` to an incorrect value | `ledger_chain_hash_mismatch` | ORP-INV-006 |
| ORP-CORR-062 | base_approved | duplicate an ordering index | `ledger_sequence_gap` | ORP-INV-016 |
| ORP-CORR-063 | base_approved | remove `ledger_evidence` block entirely | `ledger_chain_broken` | ORP-INV-006 |
| ORP-CORR-064 | base_approved | mark a partial export as full | `ledger_chain_hash_mismatch` | ORP-INV-006 |
| ORP-CORR-065 | base_approved | remove `ledger_export.json` from the package | `ledger_export_missing` | ORP-INV-006 |
| ORP-CORR-066 | base_approved | change `ledger_export.json` without changing `ledger_export_digest` | `ledger_export_digest_mismatch` | ORP-INV-006 |
| ORP-CORR-067 | base_approved | change `ledger_export.json` and recompute its digest but leave bundle ledger hash stale | `ledger_chain_hash_mismatch` | ORP-INV-006 |
| ORP-CORR-068 | base_denied or base_policy_rejected | set `export_scope=partial_view` while claiming event absence | `full_ledger_export_required` | ORP-INV-022 |
| ORP-CORR-069 | base_approved | omit event payload bytes from an export claiming `export_scope=all` | `ledger_payload_bytes_missing` | ORP-INV-006 |

### Projection Substitution Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-070 | base_approved | remove all authority digests from `run_authority` | `missing_authority_digest` | ORP-INV-005 |
| ORP-CORR-071 | base_approved | remove `approval_record_digest` | `missing_authority_digest` | ORP-INV-005 |
| ORP-CORR-072 | base_approved | change `model_invocation_evidence[0].model_invocation_digest` | `model_invocation_digest_drift` | ORP-INV-012 |
| ORP-CORR-073 | base_approved | replace authority evidence with run summary fields only | `projection_substituted_for_authority` | ORP-INV-005 |
| ORP-CORR-074 | base_approved | remove `artifacts/committed_output` from the package | `committed_artifact_missing` | ORP-INV-004 |
| ORP-CORR-075 | base_approved | change `artifacts/committed_output` bytes without changing artifact digest | `artifact_digest_mismatch` | ORP-INV-004 |

### Claim Posture Corruptions

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-080 | base_approved | request `outward_verifier_stable` with only a single verifier report | `claim_tier_not_supported` | ORP-INV-007 |
| ORP-CORR-081 | base_approved | request `outward_public_trust` without trust-boundary evidence | `claim_tier_not_supported` | ORP-INV-007 |
| ORP-CORR-082 | base_approved | request a deterministic posture without determinism evidence | `claim_tier_not_supported` | ORP-INV-007 |

### Closeout Gates

Single-turn approved closeout gate:
1. base approved package fixture exists and verifies,
2. ORP-CORR-001 through ORP-CORR-082 pass for corruptions that use `base_approved`,
3. at the original approved closeout, denial, policy-rejection, out-of-scope, and multi-turn ids could remain blocked only with explicit missing-fixture blockers.

Post-closeout denial update:
1. `base_denied_package` now exists through `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-DENIAL-FIXTURE-CLOSEOUT/`;
2. ORP-CORR-030 and the denial side of ORP-CORR-068 are active over the denied base package;
3. policy-rejection remained future-hold at that denial closeout, and out-of-scope and multi-turn ids remain future-hold unless reopened explicitly.

Post-closeout policy-rejection update:
1. `base_policy_rejected_package` now exists through `docs/projects/archive/outward-run-proof-kernel-extensions/2026-05-02-POLICY-REJECTION-FIXTURE-CLOSEOUT/`;
2. ORP-CORR-031 is active over the policy-rejected base package;
3. out-of-scope and multi-turn ids remain future-hold unless reopened explicitly.

Single-turn path-family closeout gate:
1. approval, denial, policy-rejection, and out-of-scope fixtures exist,
2. all non-deferred single-turn corruptions pass,
3. absence claims use full `export_scope=all` ledger evidence.

Lane closeout cannot claim path-family proof until the path-family gate passes.

### Multi-Turn Corruptions

These ids are reserved for Slice 07 and are not part of the single-turn closeout gate.

| ID | Base Package | Mutation | Expected Failure Code | Invariant |
|---|---|---|---|---|
| ORP-CORR-090 | base_multi_turn_approved | set second turn index equal to first turn index | `multi_turn_sequence_ordering_violated` | ORP-INV-015 |
| ORP-CORR-091 | base_multi_turn_approved | insert `turn_started(1)` before `turn_completed(0)` | `multi_turn_interleaving_violated` | ORP-INV-017 |
| ORP-CORR-092 | base_multi_turn_approved | change turn 1 prior-results digest | `cross_turn_result_linkage_missing` | ORP-INV-018 |
| ORP-CORR-093 | base_multi_turn_approved | swap declared sequence tool order | `sequence_tool_order_violated` | ORP-INV-019 |
| ORP-CORR-094 | base_multi_turn_approved | remove all events for turn 1 | `sequence_length_violated` | ORP-INV-020 |

## Required Outputs Status

| Output | Status |
|---|---|
| corruption matrix | Approved-path ids implemented; denial ORP-CORR-030 and denial ORP-CORR-068 implemented by later denial slice; policy-rejection ORP-CORR-031 implemented by later policy-rejection slice; out-of-scope and multi-turn ids remain future-hold |
| deterministic corruption helper | Implemented for approved-path ids, admitted denial ids, and admitted policy-rejection ids |
| expected reason-code mapping | Implemented for approved-path ids, admitted denial ids, and admitted policy-rejection ids |
| rerunnable corruption report | Implemented for approved, denial, and policy-rejection bases |
| assurance-case links | Approved-path links accepted; denial and policy-rejection links updated after separate slice closeouts; remaining path-family blockers tracked in future extensions |

## Exit Criteria

1. every applicable `ORP-CORR-*` entry produces the expected failure code
2. the base package for each active path still produces `result=accepted`
3. the suite proves both missing-evidence and contradictory-evidence failures
4. negative proof artifacts are listed in the assurance case index
5. the corruption report is rerunnable without manual setup
