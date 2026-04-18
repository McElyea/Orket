# Offline Trusted Run Verifier v1

Last updated: 2026-04-18
Status: Active contract
Owner: Orket Core

This spec defines the offline claim evaluator for bounded Trusted Run evidence.

It does not replace the Trusted Run Witness verifier. The witness verifier answers whether one bundle or campaign evidence surface is internally valid. The offline verifier answers which claim tier the evidence truthfully permits and which higher claims are forbidden.

## Claim Surface

Admitted ProductFlow slice identity:

1. compare scope: `trusted_run_productflow_write_file_v1`
2. operator surface: `trusted_run_witness_report.v1`
3. offline verifier report schema: `offline_trusted_run_verifier.v1`
4. witness bundle schema: `trusted_run.witness_bundle.v1`
5. witness report schema: `trusted_run_witness_report.v1`
6. replay evidence placeholder schema: `offline_replay_evidence.v1`
7. text identity placeholder schema: `offline_text_identity_evidence.v1`
8. canonical offline verifier output: `benchmarks/results/proof/offline_trusted_run_verifier.json`
9. canonical command: `python scripts/proof/verify_offline_trusted_run_claim.py --input <evidence_path>`

Admitted First Useful Workflow Slice identity:

1. compare scope: `trusted_repo_config_change_v1`
2. operator surface: `trusted_run_witness_report.v1`
3. durable contract: `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
4. canonical campaign output: `benchmarks/results/proof/trusted_repo_change_witness_verification.json`
5. canonical offline verifier output: `benchmarks/results/proof/trusted_repo_change_offline_verifier.json`
6. canonical command: `python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json`

This contract depends on:

1. `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`

## Boundary

The offline verifier MUST be inspection-only.

It MUST NOT:

1. run the workflow
2. call a model or provider
3. perform replay execution
4. mutate workflow state
5. mutate durable control-plane records
6. treat logs, review packages, graphs, or Packet projections as authority
7. publish artifacts outside its own verifier report

It MAY write its own JSON report with the repository diff-ledger writer convention.

## Supported Input Modes

The verifier supports:

| Mode | Source schema | Purpose | Highest first-slice claim |
|---|---|---|---|
| `bundle` | `trusted_run.witness_bundle.v1` | Recompute and inspect a single raw witness bundle. | `non_deterministic_lab_only` |
| `single_report` | `trusted_run_witness_report.v1` | Inspect one existing witness verifier report. | `non_deterministic_lab_only` |
| `campaign_report` | `trusted_run_witness_report.v1` with campaign fields | Inspect repeat evidence and stability signatures. | `verdict_deterministic` |
| `replay_report` | `offline_replay_evidence.v1` | Future-gated replay evidence inspection. | blocked in first slice |
| `text_identity_report` | `offline_text_identity_evidence.v1` | Future-gated byte/hash identity inspection. | blocked in first slice |

`auto` mode MUST resolve source evidence by schema and campaign fields.

Unsupported schemas MUST fail closed with `schema_version_missing_or_unsupported`.

## Report Schema

An `offline_trusted_run_verifier.v1` report MUST include:

1. `schema_version`
2. `verified_at_utc`
3. `proof_kind`
4. `input_mode`
5. `source_schema_version`
6. `input_refs`
7. `record_id`
8. `observed_path`
9. `observed_result`
10. `claim_status`
11. `claim_tier`
12. `allowed_claims`
13. `forbidden_claims`
14. `compare_scope`
15. `operator_surface`
16. `policy_digest`
17. `control_bundle_ref`
18. `evidence_ref`
19. `required_checks`
20. `passed_checks`
21. `failed_checks`
22. `missing_evidence`
23. `basis_digests`
24. `claim_ladder_basis`
25. `side_effect_free_verification`
26. `report_signature_digest`

`observed_path` MUST be one of:

1. `primary`
2. `fallback`
3. `degraded`
4. `blocked`

`observed_result` MUST be one of:

1. `success`
2. `failure`
3. `partial success`
4. `environment blocker`

`claim_status` MUST be one of:

1. `allowed`
2. `downgraded`
3. `blocked`

`report_signature_digest` MUST exclude `verified_at_utc`, `diff_ledger`, run-specific ids, session-specific paths, local absolute path prefixes, `input_refs`, and `evidence_ref`.

## Claim Ladder

Allowed claim tiers are inherited from `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`.

The first slice applies this ladder:

| Claim tier | Required evidence | First-slice behavior |
|---|---|---|
| `non_deterministic_lab_only` | One internally valid bundle or one successful single report with captured control surface, policy identity, compare scope, operator surface, final truth, effect evidence, invariant model, substrate model, and side-effect-free verification. | allowed |
| `verdict_deterministic` | A campaign report or at least two successful reports with stable contract verdict, invariant model, substrate model, and must-catch signatures on the same compare scope and operator surface. | allowed only from stable campaign evidence |
| `replay_deterministic` | Replay evidence satisfying the determinism gate policy. | forbidden unless future evidence schema is proven |
| `text_deterministic` | Verdict or replay evidence plus byte identity or declared output-hash identity on the same compare scope. | forbidden unless future evidence schema is proven |

When higher-claim evidence is missing but lower evidence is complete, the verifier MUST preserve the lower claim and report the higher claim as forbidden.

When minimum lab evidence fails, the verifier MUST set:

1. `claim_status=blocked`
2. `claim_tier=non_deterministic_lab_only`
3. `allowed_claims=[]`

## Forbidden Claim Vocabulary

The verifier MUST emit machine-readable forbidden-claim reason codes.

Minimum supported reason codes:

1. `repeat_evidence_missing`
2. `verdict_signature_not_stable`
3. `invariant_model_signature_not_stable`
4. `substrate_signature_not_stable`
5. `must_catch_outcomes_not_stable`
6. `verifier_side_effect_absence_not_mechanically_proven`
7. `compare_scope_mismatch`
8. `operator_surface_mismatch`
9. `replay_evidence_missing`
10. `replay_compare_scope_mismatch`
11. `replay_result_not_stable`
12. `text_identity_evidence_missing`
13. `text_compare_scope_mismatch`
14. `text_hash_not_stable`

Each `forbidden_claims` entry MUST include:

1. `claim_tier`
2. `reason_codes`
3. `missing_evidence`
4. `blocking_check_ids`

## Proof Requirements

Contract proof MUST include:

1. a bundle input that succeeds as `non_deterministic_lab_only`
2. a single-report input that succeeds as `non_deterministic_lab_only`
3. a campaign-report input that succeeds as `verdict_deterministic`
4. a requested replay claim that downgrades to the highest lower proven claim
5. negative examples for every `OVCL-CORR-*` corruption id from the accepted requirements
6. CLI proof that output is written with `diff_ledger`

Live proof for the first slice remains the ProductFlow Trusted Run Witness campaign:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_run_witness_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_run_witness_verification.json --claim verdict_deterministic
```

Live proof for the First Useful Workflow Slice is:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```
