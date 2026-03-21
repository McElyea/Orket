# BR03192026 Closeout

Last updated: 2026-03-19
Status: Archived
Owner: Orket Core

## Scope

This cycle closed the second behavioral-review remediation lane for the ODR semantic-validity and convergence path.

Primary closure areas:
1. remove the semantic false positives that were classifying valid requirements as invalid
2. make convergence accounting truthful across valid and invalid round histories
3. expose truthful live-runner diagnostics for mixed valid and invalid traces
4. rerun the bounded live ODR proof surfaces called out by the remediation plan
5. archive the cycle docs and clear the active roadmap lane

## Completion Gate Outcome

The cycle plan at [docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2_remediation_plan.md](docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2_remediation_plan.md) is complete:

1. all Wave 1 and Wave 2 checklist items are marked complete
2. the targeted ODR regression and determinism gate files passed after the semantic and convergence fixes
3. the exact `qwen2.5-coder:7b` / `qwen2.5:7b` live baseline reran successfully
4. the remaining `UNRESOLVED_DECISIONS` outcomes in the exact-pair baseline were genuine model-authored open questions rather than the false-positive semantic defects this cycle targeted
5. the five-run P-02 live probe no longer reproduces the prior all-`UNRESOLVED_DECISIONS` baseline
6. the cycle docs moved out of active [docs/projects/techdebt/](docs/projects/techdebt/) scope and [docs/ROADMAP.md](docs/ROADMAP.md) no longer carries this non-recurring lane

## Verification

Live proof:
1. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5-coder:7b --smoke-stream` -> `PREFLIGHT=PASS`
2. `ORKET_DISABLE_SANDBOX=1 python scripts/providers/check_model_provider_preflight.py --provider ollama --model-id qwen2.5:7b --smoke-stream` -> `PREFLIGHT=PASS`
3. `ORKET_DISABLE_SANDBOX=1 python scripts/odr/run_odr_7b_baseline.py --architect-models qwen2.5-coder:7b --auditor-models qwen2.5:7b --out .tmp/behavioral-review-round2_odr_7b_baseline.json` -> `converged=0/3`, `code_leak=0%`, `format_violation=0%`, `stop_reason_distribution={"UNRESOLVED_DECISIONS": 3}`; inspection of the live artifact showed model-authored pending decisions in `OPEN_QUESTIONS`, not semantic false positives
4. `ORKET_DISABLE_SANDBOX=1 python scripts/probes/p02_odr_isolation.py --model qwen2.5-coder:7b --runs 5 --output .tmp/behavioral-review-round2_p02_odr_isolation.json --json` -> `observed_result=success`, `stop_reason_distribution={"UNRESOLVED_DECISIONS": 1, "STABLE_DIFF_FLOOR": 4}`, `unique_raw_signatures=2`, `determinism=VARIABLE (2 unique)`

Structural proof:
1. `python -m pytest -q tests/kernel/v1/test_odr_core.py tests/kernel/v1/test_odr_determinism_gate.py tests/kernel/v1/test_odr_leak_policy_balanced.py tests/kernel/v1/test_odr_refinement_behavior.py` -> `74 passed, 3 skipped`
2. `python tools/repro_odr_gate.py --fixture tests/kernel/v1/vectors/odr/odr_torture_pack.json --seed 1729 --perm-index 0 --print-canon-hash` -> `canon_hash=d4d8e1d66653270c84d84f373dbba011574f9d1b7757f12434255df2243f57f5`
3. `python tools/repro_odr_gate.py --fixture tests/kernel/v1/vectors/odr/odr_near_miss.json --seed 1729 --perm-index 0 --print-canon-hash` -> `canon_hash=29bea1a72385d2f3abe7d44345f541abf3bd32b0c482348b4135785a13a5c403`

Governance proof:
1. `python scripts/governance/check_docs_project_hygiene.py` -> `passed`

## Not Fully Verified

1. This closeout did not rerun the full repository pytest suite.
2. The exact-pair live baseline still failed to converge on its three bundled scenarios; this archive only claims that the failures are now truthful, not that the pair is generally performant.

## Archived Documents

1. [docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2.md](docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2.md)
2. [docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2_remediation_plan.md](docs/projects/archive/techdebt/BR03192026/orket_behavioral_review_round2_remediation_plan.md)

## Residual Risk

1. `qwen2.5-coder:7b` and `qwen2.5:7b` remain weak on the exact three-scenario 7B baseline even after the semantic fixes; the lane is closed because the stop reasons are now truthful, not because the pair became broadly reliable.
2. The five-run P-02 probe is still variable across runs, so future determinism claims should continue to use the probe outputs rather than assuming stable live behavior from one successful sample.
