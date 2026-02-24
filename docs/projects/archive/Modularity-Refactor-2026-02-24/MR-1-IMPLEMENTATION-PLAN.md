# MR-1 Implementation Plan: Stabilization Baseline

Date: 2026-02-24  
Execution mode: incremental, low blast radius

## Phase 1: Defect Fixes

1. Logging isolation/hygiene
- Refactor logger setup so each log write targets intended workspace only.
- Ensure handler lifecycle does not leak file descriptors.
- Add regression test for workspace A/B cross-contamination.

2. Metrics return path
- Fix missing `return` in member metrics reader.
- Add integration-level API test using real metrics reader.

3. Webhook status typing
- Update PR-open workflow to pass canonical `CardStatus.CODE_REVIEW`.
- Add webhook test that executes PR-open path and asserts status call behavior.

## Phase 2: Guardrail Repair

1. Fix path roots in platform architecture tests.
2. Add explicit assertions that scan targets exist and contain files.
3. Align architecture policy statements:
- `docs/ARCHITECTURE.md`
- `tests/platform/test_architecture_volatility_boundaries.py`
- `scripts/check_dependency_direction.py`

## Phase 3: Validation and Closeout

1. Run targeted tests first:
- `python -m pytest -q tests/core/test_runtime_event_logging.py`
- `python -m pytest -q tests/interfaces/test_api.py -k metrics`
- `python -m pytest -q tests/adapters/test_gitea_webhook.py`
- `python -m pytest -q tests/platform`

2. Run broader lanes:
- `python -m pytest -q tests/core tests/interfaces tests/adapters tests/platform`
- `python scripts/check_dependency_direction.py`
- `python scripts/check_volatility_boundaries.py`

3. Produce closure note:
- fixed defects
- tests added
- remaining risks

## Work Slicing Guidance

1. PR slice A: logging + tests.
2. PR slice B: metrics + tests.
3. PR slice C: webhook status typing + tests.
4. PR slice D: platform guardrail path/policy alignment + tests.

## Rollback Strategy

1. If logging refactor destabilizes runtime, revert to previous logging path and keep only test-root and metrics fixes.
2. Keep each slice independently releasable.

