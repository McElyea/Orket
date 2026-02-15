# Orket Roadmap

Last updated: 2026-02-15.

## Status
Current roadmap scope is complete.

Completed priorities:
1. `P0`: Guard contract formalization + deterministic loop controls.
2. `P1`: Prompt linting + promotion governance.
3. `P2`: Runtime event envelope + model compliance reporting.
4. `P3`: Architecture boundary enforcement + maintenance checks.
5. `P4`: Operational hardening of proof cadence and reporting stability.

## Canonical Pipeline (Locked)
1. `requirements_analyst`
2. `architect`
3. `coder`
4. `code_reviewer`
5. `integrity_guard`

## Sustainment Proof (Recurring)
1. `python -m pytest tests -q`
2. `python scripts/check_dependency_direction.py`
3. `python scripts/check_volatility_boundaries.py`
4. `python -m scripts.run_live_acceptance_loop --models qwen2.5-coder:7b qwen2.5-coder:14b --iterations 1`
5. `python -m scripts.report_live_acceptance_patterns`

## Exit Criteria For New Roadmap Items
1. New item must be tied to a failing/missing mechanical proof.
2. New item must preserve role/guard ownership boundaries.
3. New item must keep dependency direction and volatility checks green.
