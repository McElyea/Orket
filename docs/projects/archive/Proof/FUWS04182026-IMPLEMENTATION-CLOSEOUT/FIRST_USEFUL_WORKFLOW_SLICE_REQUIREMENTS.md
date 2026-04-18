# First Useful Workflow Slice Requirements

Last updated: 2026-04-18
Status: Accepted, implemented, and archived
Owner: Orket Core

Archived plan: `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/FIRST_USEFUL_WORKFLOW_SLICE_REQUIREMENTS_PLAN.md`
Staging source: `docs/projects/archive/Proof/PROOF_PACKET04182026-ARCHIVE/05_FIRST_USEFUL_WORKFLOW_SLICE.md`
Primary dependency: `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
Primary dependency: `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
Primary dependency: `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
Primary dependency: `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
Primary dependency: `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

## Purpose

Define accepted requirements for Orket's first externally useful trusted workflow slice.

The slice must be understandable to an outside reviewer:

```text
Orket performed one bounded local repo config change only after approval,
validated the result deterministically, recorded the required authority
evidence, built a trusted-run witness bundle, and allowed the offline verifier
to assign the highest truthful claim tier.
```

The purpose is not to prove that Orket can write a file. The purpose is to prove that a model-assisted local change was requested, bounded by policy, approved, performed, validated, witnessed, and classified without overclaiming.

## Resolved Requirements Decisions

1. The first useful slice MUST mutate a controlled fixture repository, not the Orket source tree.
2. The workflow task MUST be: approve and verify a JSON config change under policy.
3. The fixture workspace root MUST be `workspace/trusted_repo_change/`.
4. The fixture repository root MUST be `workspace/trusted_repo_change/repo/`.
5. The bounded changed file MUST be `repo/config/trusted-change.json` relative to the fixture workspace root.
6. The deterministic validator MUST be JSON schema validation with `const` checks for required values.
7. The validator surface MUST be `trusted_repo_config_validator.v1`.
8. The compare scope MUST be `trusted_repo_config_change_v1`.
9. The operator surface MUST remain `trusted_run_witness_report.v1`.
10. The target claim tier MUST be `verdict_deterministic`.
11. A single successful run MUST remain `non_deterministic_lab_only`.
12. `replay_deterministic` and `text_deterministic` MUST remain forbidden until the evidence required by `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md` exists.
13. The accepted implementation SHOULD introduce a new proof-only workflow command instead of reusing ProductFlow's existing compare scope.
14. Existing ProductFlow, Trusted Run Witness, invariant, substrate, and offline verifier components MAY be reused as implementation building blocks, but ProductFlow's current `approved.txt` slice MUST NOT be relabeled as this useful workflow.
15. Live negative proof SHOULD cover denial and validator failure. Generated corruption tests SHOULD cover missing authority evidence and overclaim prevention.

## User-Facing Workflow

FUWS-REQ-001: The first useful workflow task MUST be externally stated as:

```text
Approve and verify a local fixture repo config change under policy.
```

FUWS-REQ-002: The workflow MUST start from a persisted card or flow whose bounded request is:

```text
Create or replace repo/config/trusted-change.json with the approved trusted
change configuration.
```

FUWS-REQ-003: The workflow MUST require operator approval before any file mutation.

FUWS-REQ-004: On approval, the workflow MUST write exactly one bounded output artifact:

```text
workspace/trusted_repo_change/repo/config/trusted-change.json
```

FUWS-REQ-005: The expected JSON object MUST be:

```json
{
  "schema_version": "trusted_repo_change.config.v1",
  "change_id": "TRUSTED-CHANGE-1",
  "approved": true,
  "risk_class": "low",
  "owner": "orket-core",
  "summary": "Approved trusted repo change fixture"
}
```

FUWS-REQ-006: The workflow MUST run one deterministic validator after the mutation and before successful final truth.

FUWS-REQ-007: The workflow MUST publish final truth only after the output artifact, effect evidence, and validator result agree.

FUWS-REQ-008: The workflow MUST emit a trusted-run witness bundle and offline verifier report.

FUWS-REQ-009: The workflow MUST be useful without requiring knowledge of Orket's internal control-plane model. Human-facing proof text MUST answer what was requested, what changed, who approved it, what policy governed it, what evidence proves the effect, what claim tier is allowed, and what would fail closed.

FUWS-REQ-010: The workflow MUST NOT mutate Orket source files, global user state, external services, or any path outside the declared fixture workspace.

## Claim Surface Requirements

FUWS-REQ-020: The accepted implementation MUST use:

| Surface | Value |
|---|---|
| compare scope | `trusted_repo_config_change_v1` |
| operator surface | `trusted_run_witness_report.v1` |
| witness bundle schema | `trusted_run.witness_bundle.v1` |
| contract verdict surface | `trusted_repo_change_contract_verdict.v1` |
| validator surface | `trusted_repo_config_validator.v1` |
| target claim tier | `verdict_deterministic` |
| single-run fallback claim tier | `non_deterministic_lab_only` |

FUWS-REQ-021: The witness bundle MUST carry `compare_scope=trusted_repo_config_change_v1`.

FUWS-REQ-022: The verifier report MUST carry `operator_surface=trusted_run_witness_report.v1`.

FUWS-REQ-023: `verdict_deterministic` MUST require a campaign report or at least two successful equivalent runs showing stable contract-verdict signature, validator signature, invariant-model signature, substrate signature, and must-catch outcome set.

FUWS-REQ-024: A single valid run MUST be useful but MUST remain `non_deterministic_lab_only`.

FUWS-REQ-025: The implementation MUST NOT claim `replay_deterministic` unless it adds replay evidence satisfying `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

FUWS-REQ-026: The implementation MUST NOT claim `text_deterministic` unless it adds byte identity or output-hash identity evidence on the same compare scope.

FUWS-REQ-027: Public or README wording MUST NOT claim broad workflow determinism from this slice.

## Deterministic Validator Requirements

FUWS-REQ-030: The deterministic validator MUST emit `trusted_repo_config_validator.v1`.

FUWS-REQ-031: The validator MUST read only the declared output artifact and the declared JSON schema.

FUWS-REQ-032: The validator MUST validate the output artifact as JSON.

FUWS-REQ-033: The validator schema MUST require:

1. `schema_version` exactly `trusted_repo_change.config.v1`
2. `change_id` exactly `TRUSTED-CHANGE-1`
3. `approved` exactly `true`
4. `risk_class` exactly `low`
5. `owner` exactly `orket-core`
6. `summary` exactly `Approved trusted repo change fixture`
7. no undeclared additional properties

FUWS-REQ-034: The validator output MUST include:

1. `schema_version`
2. `compare_scope`
3. `operator_surface`
4. `artifact_path`
5. `artifact_digest`
6. `schema_digest`
7. `validation_result`
8. `passed_checks`
9. `failed_checks`
10. `missing_evidence`
11. `validator_signature_digest`

FUWS-REQ-035: `validator_signature_digest` MUST be stable across equivalent successful runs and MUST exclude timestamps, run ids, session ids, absolute paths, and diff-ledger entries.

FUWS-REQ-036: Validator failure MUST block successful final truth and MUST produce machine-readable failure evidence.

FUWS-REQ-037: The deterministic validator MUST NOT call a model, inspect undeclared files, read mutable runtime state, or infer semantic correctness beyond the declared JSON schema.

## Evidence Requirements

FUWS-REQ-040: The accepted implementation MUST preserve or reference the following required authority evidence:

| Evidence family | Required authority | Failure semantics |
|---|---|---|
| governed input | persisted card or flow request for `TRUSTED-CHANGE-1` | missing or drifted request fails verification |
| resolved policy | policy snapshot id and policy digest | missing policy identity fails verification |
| configuration snapshot | configuration snapshot id | missing configuration identity fails verification |
| run authority | governed run record for the proof workflow | missing or mismatched run id fails verification |
| attempt authority | current attempt for the governed run | missing attempt identity fails verification |
| approval request | `approval_required_tool:write_file` request bound to the governed run and target artifact | missing or drifted approval request fails verification |
| operator action | approval or denial operator action | missing decision fails verification |
| checkpoint authority | accepted same-attempt checkpoint before mutation | missing or drifted checkpoint fails verification |
| reservation and lease | namespace reservation and lease for the fixture repo path | missing ownership evidence blocks success claims |
| effect journal | write-file effect evidence with no residual uncertainty | missing or contradicted effect evidence blocks success claims |
| output artifact | `repo/config/trusted-change.json` path plus digest | missing or wrong artifact fails verification |
| validator result | `trusted_repo_config_validator.v1` | missing or failing validator blocks success claims |
| contract verdict | `trusted_repo_change_contract_verdict.v1` | missing or drifted verdict fails verification |
| final truth | target-side final truth record | missing final truth fails verification |
| witness bundle | `trusted_run.witness_bundle.v1` | missing bundle blocks offline verification |
| offline verifier report | `offline_trusted_run_verifier.v1` | missing report blocks claim assignment proof |

FUWS-REQ-041: Review packages, run graphs, Packet 1/2 projections, logs, and human summaries MAY support review but MUST NOT replace required authority.

FUWS-REQ-042: `session_id`, workspace paths, run-summary ids, and artifact roots MUST remain locators and MUST NOT substitute for governed run authority.

FUWS-REQ-043: The accepted implementation MUST record the policy digest, control-bundle reference, compare scope, operator surface, and evidence refs as first-class fields in proof outputs.

FUWS-REQ-044: Every required artifact path in proof output MUST be workspace-relative or repo-relative unless a source contract explicitly requires a local absolute path.

## Contract Verdict Requirements

FUWS-REQ-050: `trusted_repo_change_contract_verdict.v1` MUST mechanically check:

1. the output path equals `repo/config/trusted-change.json`
2. the output artifact exists
3. the artifact digest matches the validator input
4. the JSON config validates against the declared schema
5. the approval request exists for `approval_required_tool:write_file`
6. the approval resolution is present and approved
7. the accepted checkpoint evidence exists for the same governed run
8. reservation and lease evidence covers the fixture repo target
9. effect-journal evidence exists with no residual uncertainty
10. final truth is `success` with sufficient evidence
11. the governed run id aligns across required authority surfaces

FUWS-REQ-051: Stable must-catch outcomes MUST include:

1. `missing_config_artifact`
2. `wrong_config_schema`
3. `wrong_config_content`
4. `forbidden_path_mutation`
5. `missing_approval_resolution`
6. `missing_validator_result`
7. `validator_failed`
8. `missing_effect_evidence`
9. `missing_final_truth`
10. `canonical_run_id_drift`

FUWS-REQ-052: The contract verdict signature MUST be stable across equivalent successful runs and MUST exclude timestamps, run ids, session ids, absolute paths, and generated ids.

## Failure Semantics

FUWS-REQ-060: Approval denial MUST terminal-stop the workflow before mutation.

FUWS-REQ-061: A denial proof MUST show no output artifact was created or modified and MUST record a terminal non-success final truth or explicit blocked result.

FUWS-REQ-062: Missing approval resolution MUST fail verification.

FUWS-REQ-063: Missing accepted checkpoint evidence MUST fail verification.

FUWS-REQ-064: Missing reservation or lease evidence for the fixture repo path MUST block success claims.

FUWS-REQ-065: Missing or contradicted effect evidence MUST block success claims.

FUWS-REQ-066: Validator failure MUST block successful final truth and verifier success.

FUWS-REQ-067: Any mutation outside `workspace/trusted_repo_change/repo/config/trusted-change.json` MUST fail as `forbidden_path_mutation`.

FUWS-REQ-068: Missing final truth MUST fail verification.

FUWS-REQ-069: Requested higher claims without replay or text identity evidence MUST be downgraded or forbidden by the offline verifier.

FUWS-REQ-070: All failures MUST be machine-readable, not prose-only.

## Proof Artifact Requirements

FUWS-REQ-080: The accepted implementation SHOULD use these stable output paths unless the durable spec selects better names in the same change:

| Artifact | Path |
|---|---|
| live run proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` |
| validator latest report | `benchmarks/results/proof/trusted_repo_change_validator.json` |
| witness campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` |
| witness bundle | `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json` |

FUWS-REQ-081: Rerunnable JSON proof artifacts MUST use the repository diff-ledger writer convention.

FUWS-REQ-082: Proof outputs MUST record observed path as `primary`, `fallback`, `degraded`, or `blocked`.

FUWS-REQ-083: Proof outputs MUST record observed result as `success`, `failure`, `partial success`, or `environment blocker`.

FUWS-REQ-084: Proof outputs MUST record claim tier, compare scope, operator surface, policy digest, control-bundle ref, and evidence refs.

## Proof Requirements

FUWS-REQ-090: Positive live proof MUST run the approved workflow and produce the expected JSON config, validator result, final truth, witness bundle, witness verifier report, and offline verifier report.

FUWS-REQ-091: Deterministic verdict proof MUST include either at least two equivalent successful executions or a campaign artifact proving stable contract-verdict, validator, invariant, substrate, and must-catch signatures.

FUWS-REQ-092: The first implementation handoff MUST include an offline verifier proof that allows `verdict_deterministic` for the campaign report.

FUWS-REQ-093: The first implementation handoff MUST include a denial proof showing terminal stop before mutation.

FUWS-REQ-094: The first implementation handoff MUST include a validator-failure proof showing the config artifact cannot reach successful final truth when schema validation fails.

FUWS-REQ-095: The first implementation handoff MUST include generated corruption tests for:

1. unsupported schema
2. missing approval resolution
3. missing checkpoint
4. missing reservation or lease evidence
5. missing effect evidence
6. missing validator result
7. validator failure
8. forbidden path mutation
9. missing final truth
10. run id drift
11. replay-deterministic overclaim
12. text-deterministic overclaim

FUWS-REQ-096: Mock-heavy proof MUST NOT be presented as runtime truth.

FUWS-REQ-097: Live proof is required before the implementation lane can close.

## Durable Spec Decision

FUWS-REQ-100: If these requirements are accepted, durable authority SHOULD be extracted as `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md` before implementation.

FUWS-REQ-101: The durable spec MUST reference Trusted Run Witness, Trusted Run Invariants, Control Plane Witness Substrate, Offline Trusted Run Verifier, and Determinism Gate Policy instead of duplicating their full contents.

FUWS-REQ-102: If implementation adds canonical commands, output paths, active contracts, or source-of-truth behavior, `CURRENT_AUTHORITY.md` MUST be updated in the same change.

FUWS-REQ-103: If implementation extends Trusted Run Witness or Offline Trusted Run Verifier for this compare scope, the touched durable specs MUST be updated in the same change.

## Implementation Handoff Requirements

The accepted implementation plan MUST include:

1. durable spec extraction to `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
2. any required extension to Trusted Run Witness or Offline Trusted Run Verifier specs
3. one proof-only workflow command, likely `scripts/proof/run_trusted_repo_change.py`
4. one optional campaign command, likely `scripts/proof/run_trusted_repo_change_campaign.py`
5. one deterministic validator implementation for `trusted_repo_config_validator.v1`
6. contract tests for validator, witness bundle, campaign comparison, offline verifier, and negative corruptions
7. live approved-run proof
8. live or integration denial proof
9. live or integration validator-failure proof
10. same-change authority updates for canonical commands and paths

## Acceptance State

These requirements are complete enough for user acceptance because they specify:

1. exact workflow task
2. target user-facing value
3. compare scope and operator surface
4. target and fallback claim tiers
5. deterministic validator
6. required authority evidence
7. contract verdict and must-catch outcomes
8. failure semantics
9. positive and negative proof requirements
10. durable spec extraction decision

This lane was accepted for implementation on 2026-04-18 by the user's `continue` request, implemented, and archived at `docs/projects/archive/Proof/FUWS04182026-IMPLEMENTATION-CLOSEOUT/`.
