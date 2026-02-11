# Security Audit Report (Internal)
Date: 2026-02-11
Scope: Orket runtime (`orket/`), API surface, webhook ingress, verification execution path.

## Executive Summary
- Critical hardening landed:
  - Verification fixtures now execute in isolated subprocesses with timeout and network blocking.
  - Webhook ingress now has rate limiting (`ORKET_RATE_LIMIT`).
  - CI workflow enforces tests, lint, type checks, and UTC datetime policy.
- Remaining risks:
  - Subprocess verification isolation is not yet container-grade sandboxing.
  - Broad `except Exception` handlers still exist in several modules.

## Method
- Static grep for anti-patterns and critical paths.
- Targeted test execution for verification and webhook security.
- Manual review of API/webhook auth and payload validation.

## Findings
### Closed / Mitigated
1. **Write-then-execute verification risk**: mitigated by subprocess execution with fixture path boundary checks.
2. **Webhook flood risk**: mitigated by sliding-window limiter on `/webhook/gitea`.
3. **Input validation gaps (core endpoints)**: request models present for `/system/run-active`, `/system/save`, `/webhook/gitea`, `/webhook/test`.

### Open
1. **Broad exception handling**:
   - Multiple `except Exception` blocks remain.
   - Impact: masking specific fault causes and reducing policy strictness.
2. **Verification process hardening depth**:
   - Current model blocks networking and enforces best-effort resource caps.
   - Impact: stronger than prior state but weaker than container/seccomp isolation.
3. **Boundary behavior mismatch**:
   - Historical mismatch in boundary test expectations required governance-failure behavior clarification.

## Evidence (Executed)
- `pytest tests/test_verification_subprocess.py tests/test_empirical_verification.py tests/test_webhook_rate_limit.py tests/test_api.py -q`
  - Result: passed
- CI workflow exists at `.github/workflows/quality.yml`

## Recommendations
1. Move verification execution to dedicated container sandbox with read-only mounts and no network namespace.
2. Continue exception narrowing campaign module-by-module.
3. Add dependency vulnerability scanning to CI (`pip-audit` or equivalent).
4. Perform periodic load/rate-limit tests and archive results with release artifacts.
