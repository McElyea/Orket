# Trust Reason And External Adoption Closeout

Last updated: 2026-04-18
Status: Completed and archived
Owner: Orket Core

## Outcome

The Trust Reason And External Adoption lane is implemented as a bounded docs-and-authority closeout around the shipped `trusted_repo_config_change_v1` proof slice.

The lane now provides:

1. one durable trust/publication contract
2. one proof-backed evaluator guide
3. one bounded README support section
4. synced docs index and current-authority references
5. explicit claim limits for public proof-backed wording

## Durable Authority

1. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
2. `docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md`
3. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
4. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

Contract delta:

1. `docs/architecture/CONTRACT_DELTA_TRUST_REASON_AND_EXTERNAL_ADOPTION_V1_2026-04-18.md`

## Implemented Surfaces

1. `README.md`
2. `docs/README.md`
3. `CURRENT_AUTHORITY.md`
4. `docs/specs/TRUST_REASON_AND_EXTERNAL_ADOPTION_V1.md`
5. `docs/guides/TRUSTED_REPO_CHANGE_PROOF_GUIDE.md`

## Verification

Live proof:

```text
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario denied --output benchmarks/results/proof/trusted_repo_change_denial.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario validator_failure --output benchmarks/results/proof/trusted_repo_change_validator_failure.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change.py --scenario approved --output benchmarks/results/proof/trusted_repo_change_live_run.json
ORKET_DISABLE_SANDBOX=1 python scripts/proof/run_trusted_repo_change_campaign.py
python scripts/proof/verify_offline_trusted_run_claim.py --input benchmarks/results/proof/trusted_repo_change_witness_verification.json --claim verdict_deterministic --output benchmarks/results/proof/trusted_repo_change_offline_verifier.json
```

Observed result:

1. denial proof: `observed_result=success`, `workflow_result=blocked`
2. validator-failure proof: `observed_result=success`, `workflow_result=failure`
3. approved run proof: `observed_result=success`, `workflow_result=success`
4. campaign proof: `observed_result=success`, `claim_tier=verdict_deterministic`
5. offline verifier proof: `observed_result=success`, `claim_status=allowed`, `claim_tier=verdict_deterministic`

## Remaining Blockers Or Drift

The shipped public trust surface remains intentionally bounded. It truthfully covers `trusted_repo_config_change_v1` only, stops at `verdict_deterministic`, and does not prove replay determinism, text determinism, arbitrary user workflows, or whole-runtime mathematical soundness.
