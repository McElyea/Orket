# Trusted Repo Change Proof Guide

Last reviewed: 2026-04-18

Use this guide to evaluate the current proof-backed trust slice without inferring broader product claims.

## Current Truth

- Canonical trust reason: `Orket makes bounded workflow success independently checkable.`
- Compare scope: `trusted_repo_config_change_v1`
- Current truthful claim ceiling: `verdict_deterministic`
- Current proof posture: proof-only and fixture-bounded
- Not yet proven for this slice: replay determinism and text determinism

The practical reason to trust this slice over a runtime with similar logs is not that Orket has more data. It is that approval, effect, validator, final-truth, and claim-tier evidence are packaged so stronger claims fail closed when the evidence is missing.

## Run The Evaluator Path

1. Run one negative proof:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario denied --output benchmarks/results/proof/trusted_repo_change_denial.json
```

Expected result: `observed_result=success`, `workflow_result=blocked`.

2. Run the validator-failure proof:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario validator_failure --output benchmarks/results/proof/trusted_repo_change_validator_failure.json
```

Expected result: `observed_result=success`, `workflow_result=failure`.

3. Run the approved path:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario approved --output benchmarks/results/proof/trusted_repo_change_live_run.json
```

Expected result: `observed_result=success`, `workflow_result=success`.

4. Run the two-run campaign:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
```

Expected result: `observed_result=success`, `claim_tier=verdict_deterministic`.

5. Run the offline verifier:

```text
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

Expected result: `observed_result=success`, `claim_status=allowed`, `claim_tier=verdict_deterministic`.

## Inspect The Authority Artifacts

| Artifact | Path | Role |
|---|---|---|
| approved live proof | `benchmarks/results/proof/trusted_repo_change_live_run.json` | shows the approved bounded run completed |
| validator report | `benchmarks/results/proof/trusted_repo_change_validator.json` | shows deterministic config validation passed on the bounded output |
| denial proof | `benchmarks/results/proof/trusted_repo_change_denial.json` | shows the workflow terminal-stops before mutation |
| validator-failure proof | `benchmarks/results/proof/trusted_repo_change_validator_failure.json` | shows failed validation blocks success |
| campaign report | `benchmarks/results/proof/trusted_repo_change_witness_verification.json` | shows repeated evidence stability and the current claim tier |
| offline verifier report | `benchmarks/results/proof/trusted_repo_change_offline_verifier.json` | shows the highest truthful allowed claim from shipped evidence |

For the witness bundle, open `benchmarks/results/proof/trusted_repo_change_live_run.json`, read the emitted `session_id`, then inspect:

```text
workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json
```

Treat the witness bundle, campaign report, and offline verifier report as the primary proof authority. Treat this guide, README text, and closeout notes as support-only.

## What This Slice Proves

This slice proves that `trusted_repo_config_change_v1` can:
1. require approval before mutation
2. emit approval, effect, validator, and final-truth evidence
3. package that evidence into a witness bundle
4. reach `verdict_deterministic` through a stable two-run campaign
5. refuse stronger claims when the evidence is missing

## What This Slice Does Not Prove

This slice does not prove:
1. arbitrary user workflows are trusted-run verified
2. all Orket runs are deterministic
3. replay determinism for this slice
4. text determinism for this slice
5. model output correctness in general
6. mathematical soundness of the whole runtime
