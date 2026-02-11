# Orket Security and Governance

This document defines baseline security and governance requirements.

## 1. Credential Boundary
- Store secrets in `.env`.
- Keep secrets out of source control.
- Do not hardcode credentials in runtime code or committed config.

## 2. Filesystem Boundary
- Runtime file operations stay inside approved workspace boundaries.
- Path traversal outside approved roots is denied.
- Write operations are limited to authorized output locations.

## 3. State and Governance Boundary
- State transitions must pass state machine rules.
- Tool calls must pass tool-gate validation before execution.
- Governance violations block progression.

## 4. Reliability Boundary
- Runtime exceptions must be explicit and typed where possible.
- Failures should be surfaced with actionable error context.

## 5. Auditability
- Session activity and runtime actions must be observable through logs and datastore records.
- Operational run procedures are maintained in `docs/RUNBOOK.md`.
