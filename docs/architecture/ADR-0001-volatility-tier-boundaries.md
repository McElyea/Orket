# ADR-0001: Volatility Tier Boundaries

Date: 2026-02-13  
Status: Accepted

## Context
Orket has accumulated mixed-volatility modules across orchestration, integrations, policies, and interfaces. This makes dependency direction unclear and refactors high-risk.

The architecture model requires decomposition by rate of change and strict inward dependency direction.

## Decision
Adopt explicit volatility tiers for `orket/`:
1. `core`: lowest volatility domain/contracts/policies.
2. `application`: workflow use-cases and coordination.
3. `adapters`: external integrations and implementations.
4. `interfaces`: API/CLI/webhook entry points.
5. `platform`: cross-cut runtime/config/observability infrastructure.

Boundary rules:
1. `core` must not import `application`, `adapters`, or `interfaces`.
2. `application` must not import `interfaces`.
3. `adapters` must not import `interfaces`.
4. `interfaces` may depend on inner tiers but should not hold business policy logic.

## Consequences
Positive:
1. Safer refactoring through explicit dependency direction.
2. Clear ownership by volatility and change frequency.
3. Better test lane separation (unit/integration/acceptance/live).

Trade-offs:
1. Temporary compatibility shims are needed during migration.
2. Additional architecture checks are required in CI.
3. Short-term code churn while modules are relocated.

## Enforcement
1. Architecture boundary tests in `tests/platform/test_architecture_volatility_boundaries.py`.
2. Dependency-direction script: `scripts/check_dependency_direction.py`.
3. Canonical dependency policy contract: `model/core/contracts/dependency_direction_policy.json`.
4. CI workflow must run these checks before quality/test jobs.
5. Legacy migration uses a ratcheting budget (`legacy_edge_budget`) that is enforced as non-regression in CI.

## Migration Notes
1. Move low-volatility modules first (`state_machine`, `records`, repository contracts, tool gate).
2. Keep legacy import shims until all call sites migrate.
3. Remove compatibility shims in later roadmap phases.
