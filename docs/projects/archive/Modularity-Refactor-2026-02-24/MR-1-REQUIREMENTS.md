# MR-1 Requirements: Stabilization Baseline

Date: 2026-02-24  
Type: contract-preserving refactor/stabilization

## Objective

Eliminate known critical runtime defects and restore trustworthy architecture/test guardrails before deeper modular decomposition.

## In Scope

1. Logging isolation correctness.
2. Run metrics endpoint correctness.
3. Webhook PR-open status transition correctness.
4. Architecture guardrail test root/path correctness.
5. Architecture policy source-of-truth alignment (doc/test/script).
6. Targeted test additions for every fixed defect class.

## Out of Scope

1. Breaking public API contracts.
2. Large package split/republish.
3. Deep business logic redesign.

## Functional Requirements

1. Logging events emitted to workspace A must not appear in workspace B logs.
2. Logging must not keep unbounded per-workspace file handlers attached.
3. `/v1/runs/{session_id}/metrics` must return a non-null JSON object when logs exist.
4. PR-open webhook path must update card state using canonical `CardStatus` type.
5. Platform boundary tests must scan repository paths, not `tests/` pseudo-roots.
6. Guard tests must assert scan roots exist and include at least one Python file.

## Quality Requirements

1. Existing API/CLI endpoint contracts preserved.
2. Existing card status vocabulary preserved.
3. No regression in current passing adapter/interface suites.
4. New tests must fail before fix and pass after fix.

## Verification Requirements

1. Add/extend tests for:
- multi-workspace log isolation
- metrics reader real return path
- webhook PR-open status update path
- architecture guard path sanity checks

2. Run at minimum:
- `python -m pytest -q tests/core tests/interfaces tests/adapters tests/platform`
- `python scripts/check_dependency_direction.py`
- `python scripts/check_volatility_boundaries.py`

## Acceptance Criteria

1. All critical findings tagged in review as runtime blockers are closed.
2. Architecture guard tests can no longer pass with empty/nonexistent scan roots.
3. CI-equivalent local quality commands are green for touched lanes.
4. No external contract break introduced.

