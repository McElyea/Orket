# First Useful Workflow Slice Closeout

Last updated: 2026-04-18
Status: Completed and archived
Owner: Orket Core

## Outcome

The First Useful Workflow Slice is implemented as a proof-only trusted repo config change workflow.

The slice now proves:

1. a bounded fixture repo config change can be approved before mutation
2. denial terminal-stops before mutation
3. validator failure blocks successful final truth
4. a successful run emits `trusted_run.witness_bundle.v1`
5. a campaign over two equivalent runs reaches `verdict_deterministic`
6. the offline verifier allows that claim for `trusted_repo_config_change_v1`
7. replay and text deterministic overclaims remain forbidden without required evidence

## Durable Authority

Durable contract:

1. `docs/specs/FIRST_USEFUL_WORKFLOW_SLICE_V1.md`
2. `docs/specs/TRUSTED_RUN_WITNESS_V1.md`
3. `docs/specs/TRUSTED_RUN_INVARIANTS_V1.md`
4. `docs/specs/CONTROL_PLANE_WITNESS_SUBSTRATE_V1.md`
5. `docs/specs/OFFLINE_TRUSTED_RUN_VERIFIER_V1.md`

Contract delta:

1. `docs/architecture/CONTRACT_DELTA_FIRST_USEFUL_WORKFLOW_SLICE_V1_2026-04-18.md`

## Implemented Surfaces

1. `scripts/proof/run_trusted_repo_change.py`
2. `scripts/proof/run_trusted_repo_change_campaign.py`
3. `scripts/proof/trusted_repo_change_contract.py`
4. `scripts/proof/trusted_repo_change_verifier.py`
5. `scripts/proof/trusted_repo_change_workflow.py`
6. `scripts/proof/trusted_repo_change_offline.py`
7. `scripts/proof/verify_offline_trusted_run_claim.py`

## Proof Artifacts

1. `benchmarks/results/proof/trusted_repo_change_live_run.json`
2. `benchmarks/results/proof/trusted_repo_change_validator.json`
3. `benchmarks/results/proof/trusted_repo_change_denial.json`
4. `benchmarks/results/proof/trusted_repo_change_validator_failure.json`
5. `benchmarks/results/proof/trusted_repo_change_witness_verification.json`
6. `benchmarks/results/proof/trusted_repo_change_offline_verifier.json`
7. `workspace/trusted_repo_change/runs/<session_id>/trusted_run_witness_bundle.json`

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

Test proof:

```text
ORKET_DISABLE_SANDBOX=1 python -m pytest -q tests/scripts/test_first_useful_workflow_slice.py tests/scripts/test_offline_trusted_run_verifier.py tests/scripts/test_trusted_run_witness.py tests/scripts/test_control_plane_witness_substrate.py
```

Observed result: `92 passed`.

## Remaining Blockers Or Drift

The implemented slice is proof-only. It truthfully proves the bounded fixture workflow and offline claim ladder, not broad Orket workflow determinism or production UI adoption.
