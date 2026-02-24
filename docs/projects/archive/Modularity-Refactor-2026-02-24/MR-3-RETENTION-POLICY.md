# MR-3 Retention Policy (Temp Repo + Local Dry-Run)

Date: 2026-02-24  
Mode: test-first, dry-run by default

## Objective

Define and enforce deterministic retention behavior for multi-purpose artifact storage without introducing destructive defaults.

## Namespaces

1. `smoke/`
- Profile startup/test evidence.

2. `checks/`
- Policy and gate output artifacts.

3. `artifacts/`
- High-volume benchmark/runtime artifacts.

4. `latest/`
- Pointers/aliases only.

## Retention Rules

1. `smoke/`
- TTL: 14 days
- Keep newest 50 per profile minimum

2. `checks/`
- TTL: 60 days
- Always keep newest `pass` and newest `fail` per check when present

3. `artifacts/`
- TTL: 30 days
- Optional size cap: 200 GB default
- If over cap, prune oldest unpinned first

4. `latest/`
- Never delete by retention planner

5. Global protections
- Never delete `pinned=true`
- Never delete newest smoke run per profile
- Never delete newest checks run per status (`pass`/`fail`) per check

## Scripts

1. `scripts/retention_plan.py`
- Generates dry-run retention action plan from:
  - local filesystem scan (`--root`) or
  - inventory JSON (`--inventory`)
- Writes plan JSON (default: `benchmarks/results/retention_plan.json`)

2. `scripts/check_retention_policy.py`
- Validates retention plan safety invariants
- Writes policy-check JSON (default: `benchmarks/results/retention_policy_check.json`)
- `--require-safety` exits non-zero on violations

## Default Test Steps For Runs

1. `python scripts/retention_plan.py --out benchmarks/results/retention_plan.json`
2. `python scripts/check_retention_policy.py --plan benchmarks/results/retention_plan.json --out benchmarks/results/retention_policy_check.json --require-safety`
3. `python -m pytest -q tests/runtime/test_retention_policy.py`
4. `python -m pytest -q tests/application/test_retention_scripts.py`

## Activation Path

1. Keep dry-run as default for all environments.
2. Add apply mode later under explicit flag and staged rollout.
3. Publish plan/check artifacts to temp repo paths (`checks/` namespace) for auditability.

