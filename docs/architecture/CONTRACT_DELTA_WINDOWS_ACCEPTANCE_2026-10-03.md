# Windows refactor acceptance scope

## Summary

- Change title: User-directed Windows-only ATG-v1 acceptance.
- Owner: Orket Core.
- Date: 2026-10-03 (America/Denver).
- Affected contracts: verification/platform requirements in
  `docs/specs/RUNTIME_EXECUTION_RESULT_CONTRACT.md`, the status pointer in
  `docs/specs/API_RUNTIME_LIFECYCLE.md`, contributor execution guidance and the
  canonical architectural-truth plan/worksets.

## Delta

- Previous requirement: installed Windows/Linux Python 3.11/3.12 proof, Linux
  host-clock qualification and complete hosted Gitea Quality were ATG-09 gates.
- Current requirement: Windows is the sole refactor acceptance target. Retain
  native Windows source quality, installed/public-path evidence on Python 3.11/3.12
  and actual llama.cpp library-flow proof. Local execution can establish these
  outcomes without hosted runner availability. Preserve the full source selection,
  89-percent combined coverage floor, assertions, deadlines and declared skips.
- Authority: the user explicitly asked to remove the blocker and stop trying to
  support Linux if Windows works. This withdraws Linux/WSL and hosted cross-platform
  obligations from this refactor; it does not label them passed or waive Windows
  failures. Windows installed proof already passes at its recorded scope; current
  full-source coverage after the reload repair remains required.
- No runtime APIs, result vocabulary, ownership/cleanup behavior, POSIX backend
  implementation or existing CI definitions change. No Mac/Linux support, hosted
  green status, new Windows Docker target or whole-product conformance is claimed.

## Migration Plan

1. Effective immediately for ATG-v1; no caller/API migration is required.
2. Follow the updated ATG-09 card and Windows two-day schedule. Retire prior Linux
   clock/runner admission instructions and pending runner requests. Do not activate
   infrastructure to satisfy a withdrawn requirement.
3. Reuse accepted Windows and provider receipts only after relevant-input checks.
   Run the current full native Windows quality/coverage selection and applicable
   canonical local checks before ATG-09 acceptance; then publish ATG-10 separately.
4. Preserve exact earlier plan bytes in
   `docs/projects/archive/architectural-truth/AT10032026-WINDOWS-SCOPE/` and retain
   workset observations/failed receipts as history. Eight of ten goals remain
   complete at this amendment; historical missing proof remains missing.

## Rollback Plan

1. Reopen Linux/platform acceptance only on explicit user direction.
2. Define the requested platform scope and prerequisites in the canonical plan,
   using the preserved history without silently reactivating expired runner windows.
3. No product data, installed package or infrastructure state changes in this
   amendment; historical receipts require no reconstruction or data rollback.

## Versioning Decision

- Patch checkpoint: v0.6.142, effective 2026-10-03.
- Runtime compatibility is preserved; required refactor verification scope changes
  by explicit user decision. No operator or extension-author action is required.
- Structural validation and retained Windows evidence support this documentation
  change. It is not a fresh full-suite result or ATG-09/10 completion claim.
