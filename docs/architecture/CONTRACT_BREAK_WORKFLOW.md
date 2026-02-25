# Contract Break Workflow

## Scope
Applies to any pull request that introduces a boundary-policy break, dependency-direction exception, or contract-incompatible change.

## Required Inputs
1. Completed proposal using `docs/architecture/CONTRACT_DELTA_TEMPLATE.md`.
2. Updated contract artifact(s) in `model/core/contracts/`.
3. Migration and rollback evidence (tests, scripts, or runbook links).

## Merge Gates
1. Dependency and volatility checks remain green.
2. Contract delta proposal is linked in the PR description.
3. Versioning decision is explicit and accepted.
4. Roadmap/project status docs reflect the contract change.

## Review Expectations
1. Reject silent exceptions and undocumented breakages.
2. Require deterministic tests for the new boundary behavior.
3. Confirm rollback steps are executable with current tooling.
