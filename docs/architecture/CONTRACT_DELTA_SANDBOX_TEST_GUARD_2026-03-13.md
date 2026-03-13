# Contract Delta Proposal

## Summary
- Change title: Pytest sandbox fail-closed default and live cleanup gate hardening
- Owner: Orket Core
- Date: 2026-03-13
- Affected contract(s): `docs/TESTING_POLICY.md`, `docs/CONTRIBUTOR.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: ordinary pytest runs may trigger real Docker sandbox creation unless each test remembers to set `ORKET_DISABLE_SANDBOX=1`; the live leak gate checks `docker-compose ls`, which can miss leftover `Created` containers after compose metadata is gone.
- Proposed behavior: the general pytest suite sets `ORKET_DISABLE_SANDBOX=1` by default through `tests/conftest.py`; only explicit live sandbox acceptance work may create real `orket-sandbox-*` resources; the leak gate verifies actual Docker containers, networks, and volumes rather than only compose project listings.
- Why this break is required now: the prior contract created false-green cleanup confidence and leaked real Docker resources from non-sandbox tests, consuming operator trust and host privileges.

## Migration Plan
1. Compatibility window: immediate for the pytest suite on merge.
2. Migration steps:
   - rely on the default pytest sandbox-disable fixture for ordinary tests
   - explicitly opt into live sandbox lifecycle tests when Docker use is intentional
   - keep leak verification on actual Docker resources
3. Validation gates:
   - targeted regression tests for previously leaking orchestration paths
   - contract tests for contributor/authority docs
   - live leak gate remains opt-in and cleanup-sensitive

## Rollback Plan
1. Rollback trigger: legitimate non-live tests require automatic sandbox creation and no explicit opt-in path is available.
2. Rollback steps:
   - remove the autouse pytest fixture in `tests/conftest.py`
   - revert the testing-policy and contributor/authority docs
   - reassess a narrower opt-in/opt-out boundary
3. Data/state recovery notes: leaked `orket-sandbox-*` Docker resources must still be removed manually or by cleanup tooling; rollback does not restore them automatically.

## Versioning Decision
- Version bump type: patch
- Effective version/date: next non-docs release after 2026-03-13
- Downstream impact: tests that relied on implicit sandbox creation must now opt in explicitly or override `ORKET_DISABLE_SANDBOX`.
