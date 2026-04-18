# First Useful Workflow Slice v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines Orket's first externally understandable trusted workflow slice.

The slice answers one bounded question:

```text
Can Orket approve, perform, validate, witness, and offline-verify one useful
local fixture repo config change without claiming more than the evidence supports?
```

This contract does not prove broad workflow determinism, full replay determinism, text determinism, remote provider behavior, UI behavior, or general ProductFlow eligibility.

## Dependencies

This contract depends on:

1. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

Those specs remain the authority for claim tiers, witness bundle shape, invariant model shape, substrate model shape, and offline claim assignment. This spec defines the new compare scope and useful workflow contract.

## Claim Surface

The admitted slice identity is:

| Surface | Value |
|---|---|
| compare scope | `trusted_repo_config_change_v1` |
| operator surface | `trusted_run_witness_report.v1` |
| witness bundle schema | `trusted_run.witness_bundle.v1` |
| contract verdict surface | `trusted_repo_change_contract_verdict.v1` |
| validator surface | `trusted_repo_config_validator.v1` |
| invariant model surface | `trusted_run_invariant_model.v1` |
| substrate model surface | `control_plane_witness_substrate.v1` |
| target claim tier | `verdict_deterministic` |
| single-run fallback claim tier | `non_deterministic_lab_only` |

The canonical operator commands are:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

The stable proof artifact paths are:

| Artifact | Path |
|---|---|
| live run proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` |
| validator latest report | `benchmarks/results/proof/trusted_repo_change_validator.json` |
| witness campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` |
| witness bundle | `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json` |

Rerunnable JSON outputs MUST use the repository diff-ledger writer convention.

## Workflow Contract

The workflow task is:

```text
Approve and verify a local fixture repo config change under policy.
```

The workflow MUST:

1. start from a persisted proof flow request for `TRUSTED-CHANGE-1`
2. require operator approval before mutation
3. mutate only `workspace/trusted_repo_change/repo/config/trusted-change.json`
4. terminal-stop before mutation when approval is denied
5. run the deterministic validator after mutation and before success final truth
6. publish final truth only after artifact, effect evidence, and validator result agree
7. emit a witness bundle and an offline verifier report
8. keep all proof paths repo-relative or workspace-relative unless a source contract requires otherwise

The workflow MUST NOT mutate Orket source files, global user state, external services, or paths outside the declared fixture workspace.

## Expected Config

The expected JSON object is:

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

No undeclared additional properties are allowed.

## Validator Contract

`trusted_repo_config_validator.v1` MUST:

1. read only the declared config artifact and the declared expected schema
2. validate the artifact as JSON
3. require exact `const` values for every expected field
4. reject additional properties
5. emit machine-readable pass and fail evidence
6. compute `validator_signature_digest` from stable material that excludes timestamps, run ids, session ids, absolute paths, and diff-ledger entries

The validator report MUST include:

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

Validator failure MUST block successful final truth.

## Required Authority Evidence

The witness bundle MUST preserve or reference:

| Evidence family | Required authority | Failure semantics |
|---|---|---|
| governed input | persisted proof flow request for `TRUSTED-CHANGE-1` | missing or drifted request fails verification |
| resolved policy | policy snapshot id and policy digest | missing policy identity fails verification |
| configuration snapshot | configuration snapshot id | missing configuration identity fails verification |
| run authority | governed proof workflow run record | missing or mismatched run id fails verification |
| attempt authority | current attempt for the governed run | missing attempt identity fails verification |
| approval request | `approval_required_tool:write_file` request bound to the target artifact | missing or drifted request fails verification |
| operator action | approval or denial operator action | missing decision fails verification |
| checkpoint authority | accepted same-attempt checkpoint before mutation | missing or drifted checkpoint fails verification |
| reservation and lease | fixture repo path reservation and lease | missing ownership evidence blocks success claims |
| effect journal | write-file effect evidence with no residual uncertainty | missing or contradicted effect evidence blocks success claims |
| output artifact | `repo/config/trusted-change.json` path plus digest | missing or wrong artifact fails verification |
| validator result | `trusted_repo_config_validator.v1` | missing or failing validator blocks success claims |
| contract verdict | `trusted_repo_change_contract_verdict.v1` | missing or drifted verdict fails verification |
| final truth | target-side final truth record | missing final truth fails verification |
| witness bundle | `trusted_run.witness_bundle.v1` | missing bundle blocks offline verification |
| offline verifier report | `offline_trusted_run_verifier.v1` | missing report blocks claim assignment proof |

Review packages, run graphs, Packet projections, logs, and human summaries MAY support review but MUST NOT replace required authority.

## Contract Verdict

`trusted_repo_change_contract_verdict.v1` MUST mechanically check:

1. output path equals `repo/config/trusted-change.json`
2. the output artifact exists
3. the artifact digest matches the validator input
4. the JSON config validates against the declared schema
5. approval request exists for `approval_required_tool:write_file`
6. approval resolution is present and approved
7. accepted checkpoint evidence exists for the same governed run
8. reservation and lease evidence covers the fixture repo target
9. effect-journal evidence exists with no residual uncertainty
10. final truth is `success` with sufficient evidence
11. governed run id aligns across required authority surfaces

The stable must-catch outcomes are:

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

The verdict signature MUST be stable across equivalent successful executions and MUST exclude timestamps, run ids, session ids, absolute paths, and generated ids.

## Claim Rules

A single valid run remains `non_deterministic_lab_only`.

`verdict_deterministic` requires a campaign report or at least two successful equivalent runs with stable:

1. contract-verdict signature
2. validator signature
3. invariant-model signature
4. substrate signature
5. must-catch outcome set

`replay_deterministic` and `text_deterministic` remain forbidden for this slice unless future evidence satisfies `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

The offline verifier MUST preserve lower proven claims and downgrade or block unsupported higher claims.

## Failure Semantics

The implementation MUST fail closed when:

1. approval is denied
2. approval resolution is missing
3. checkpoint evidence is missing
4. reservation or lease evidence is missing
5. effect evidence is missing
6. validator evidence is missing
7. validation fails
8. any path outside `repo/config/trusted-change.json` is mutated
9. final truth is missing
10. run id drifts across authority surfaces
11. replay or text deterministic claims are requested without required evidence

All failures MUST be machine-readable.
