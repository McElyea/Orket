# Live Runtime Proof Recovery Plan

Last updated: 2026-03-30
Status: Active
Owner: Orket Core

## Purpose

Define the standing live-proof maintenance path for active recurring techdebt work without reopening archived runtime-stability closeout packets implicitly.

This runbook exists to keep one current live maintenance proof surface explicit:
1. the canonical live sandbox baseline in Section E of `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`

## Active Standing Proof Surface

The current standing live maintenance command is:
1. `python scripts/techdebt/run_live_maintenance_baseline.py --baseline-id <baseline_id> --strict`

This command is the active maintenance runner for live sandbox baseline proof.

Its canonical live target is:
1. `tests/acceptance/test_sandbox_orchestrator_live_docker.py::test_live_create_health_and_cleanup_flow`

Its required live environment toggle is:
1. `ORKET_RUN_SANDBOX_ACCEPTANCE=1`

## Expected Evidence

The runner records evidence under:
1. `benchmarks/results/techdebt/live_maintenance_baseline/<baseline_id>/`

Expected artifacts:
1. `commands.txt`
2. `environment.json`
3. `stdout.log`
4. `stderr.log`
5. `result.json`

The truthful green baseline is:
1. `proof_type=live`
2. `path=primary`
3. `result=success`

If Docker preflight fails or the live pytest target skips, the result must remain:
1. `path=blocked`
2. `result=environment blocker`

## Relationship To Archived Recovery Packets

The archived runtime-stability live proof recovery packet remains historical authority only:
1. `docs/projects/archive/runtime-stability-closeout/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`

That archived packet records the closed Claim A/B/C/D/F/G live evidence and the historical Claim E carry-forward state.

It is not the active recurring maintenance runbook.
It must not be treated as permission to reopen runtime-stability compare hardening, provider-specific live proof, or older claim packets silently.

## When To Use This Runbook

Use this runbook when:
1. Section E of `docs/projects/techdebt/Recurring-Maintenance-Checklist.md` is triggered
2. sandbox orchestration, lifecycle, cleanup, or reconciliation behavior changes
3. a maintenance pass needs fresh live proof of the current sandbox baseline

Do not use this runbook as a substitute for:
1. provider-model-specific live evidence campaigns
2. replay-compare remediation for archived runtime-stability claims
3. broader acceptance or release sign-off outside the sandbox baseline named above

## Escalation And Reopen Rules

If the live baseline runner returns anything other than `path=primary` and `result=success`:
1. record the exact blocker or failure in the generated evidence
2. keep the result truthful as `failure` or `environment blocker`
3. open or update a scoped remediation lane only when the recurring checklist requires one

If future work needs a different live proof surface, it must:
1. name the new canonical command explicitly
2. update `docs/projects/techdebt/Recurring-Maintenance-Checklist.md` in the same change
3. avoid treating archived runtime-stability packets as active standing authority

## Source Authorities

1. `docs/projects/techdebt/Recurring-Maintenance-Checklist.md`
2. `docs/projects/techdebt/README.md`
3. `scripts/techdebt/run_live_maintenance_baseline.py`
4. `docs/projects/archive/runtime-stability-closeout/LIVE-RUNTIME-PROOF-RECOVERY-PLAN.md`
