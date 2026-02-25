# Docs Gate Implementation Plan

Date: 2026-02-24  
Execution mode: bounded deterministic slice delivery

## Phase 1: Contract Skeleton
1. Implement CLI argument parsing for `scripts/docs_lint.py`.
2. Implement deterministic file discovery for scoped markdown paths.
3. Implement result envelope and stable violation sorting.
4. Add usage errors and `E_DOCS_USAGE`.

## Phase 2: DL1-DL3 Checks
1. Implement relative-link extraction and filtering rules for `DL1`.
2. Implement canonical registry existence validation for `DL2`.
3. Implement active-doc header validation for `DL3`.
4. Emit stable error codes and actionable messages per violation.

## Phase 3: Acceptance and Unit Coverage
1. Add acceptance scripts under `tests/acceptance/docs_gate/` for `DL0-DL3`.
2. Add python unit tests for parsing edge cases and sort determinism.
3. Verify script exits and JSON report schema in tests.

## Phase 4: Verify Profile and CI Wiring
1. Add docs-lint command to a deterministic verify profile.
2. Add quality workflow smoke invocation for docs gate.
3. Add workflow test assertions to prevent command regression.

## Phase 5: Strict Cross-Reference Expansion (DG-4)
1. Add strict-mode cross-reference token checks for error/gate contracts.
2. Add strict-mode tests for pass/fail fixtures.
3. Promote strict mode into CI docs gate command once stable.

## Validation Commands
1. `python scripts/docs_lint.py --project core-pillars`
2. `python -m pytest -q tests/acceptance/docs_gate tests/platform/test_quality_workflow_gates.py`
3. `python scripts/check_dependency_direction.py --legacy-edge-enforcement fail`
4. `python scripts/check_volatility_boundaries.py`
5. `python -m pytest -q`

## Risks and Controls
1. Link parsing false positives in fenced code blocks.
- Control: exclude fenced code sections in parser pass.

2. Registry source ambiguity.
- Control: define one canonical registry path in implementation constants.

3. Scope creep into generalized doc quality tooling.
- Control: enforce DL1-DL3 only for v1 and defer expansions to future milestones.
