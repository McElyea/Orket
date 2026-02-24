# MR-3 Implementation Plan: Boundary Hardening and Contract Governance

Date: 2026-02-24  
Execution mode: policy-first, test-enforced

## Phase 1: Policy Canonicalization

1. Choose final boundary policy, including explicit decision on `application -> adapters`.
2. Update architecture docs to canonical policy.
3. Encode same policy in dependency-direction script and platform tests.

## Phase 2: Checker Expansion

1. Extend dependency checker layer mapping to all active top-level packages.
2. Add failure on unknown layer/module classification.
3. Add report output (`json` + `md`) with:
- layer edges
- forbidden edges
- unknown classifications

## Phase 3: Test and CI Enforcement

1. Add tests that fail when:
- scan roots missing/empty
- policy definitions diverge
- forbidden-edge fixture is introduced

2. Ensure checks run in both architecture gate and full quality jobs.

## Phase 4: Contract Governance Workflow

1. Add template for contract-delta proposal.
2. Add rule: no boundary-breaking merge without migration note.
3. Add periodic boundary-drift review cadence.

## Validation Commands

1. `python scripts/check_dependency_direction.py`
2. `python scripts/export_dependency_graph.py`
3. `python -m pytest -q tests/platform`
4. `python scripts/check_volatility_boundaries.py`

## Work Slicing Guidance

1. PR slice A: policy alignment (docs/tests/scripts).
2. PR slice B: checker expansion + unknown-layer failure.
3. PR slice C: CI/report artifacts.
4. PR slice D: governance templates and contributor process updates.

## Risks and Mitigation

1. Risk: stricter checker surfaces large backlog immediately.
- Mitigation: staged enforcement mode (`warn` then `fail`) with deadline.

2. Risk: unresolved policy disagreement blocks progress.
- Mitigation: force explicit architecture decision before Phase 2 begins.

