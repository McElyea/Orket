# Contract Delta: Tech Debt Remediation 2026-04-25

## Summary
- Change title: Tech debt remediation authority updates
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/specs/SUPERVISOR_RUNTIME_APPROVAL_CHECKPOINT_V1.md`, `docs/specs/SUPERVISOR_RUNTIME_OPERATOR_APPROVAL_SURFACE_V1.md`, `docs/specs/ORKET_DETERMINISM_GATE_POLICY.md`, `docs/specs/PROMPT_REFORGER_GENERIC_SERVICE_CONTRACT.md`, `docs/requirements/sdk/VERSIONING.md`, `docs/API_FRONTEND_CONTRACT.md`, `docs/SECURITY.md`, `CURRENT_AUTHORITY.md`

## Delta
- Current behavior: approval checkpoint authority admitted kernel `NEEDS_APPROVAL`, `write_file`, and `create_issue`; projection packs had no named outbound policy gate; behavioral claim docs did not explicitly block unproven sub-7B portability, unproven ODR text identity, or SDK/core version drift.
- Proposed behavior: admit `create_directory` as one additional bounded governed turn-tool approval slice; apply an outbound projection redaction gate before kernel projection digesting; document sub-7B Prompt Reforger portability as unsupported until exact corpus evidence clears; require ODR/local-model text identity proof before `text_deterministic`; define the SDK/core compatibility window.
- Why this break is required now: the remediation plan identified stale authority and policy gaps that could create false confidence about approval scope, outbound privacy posture, determinism, portability, and SDK compatibility.

## Migration Plan
1. Compatibility window: immediate for docs and tests; no API route or approval decision payload migration is required.
2. Migration steps: update runtime gates, update durable contracts, and keep existing approval request shape `tool_approval` plus `approval_required_tool:<tool_name>`.
3. Validation gates: targeted pytest for provider extraction, SQLite migrations, approval-tool admission, outbound policy gate, behavioral claim docs, SDK docs, workflow coverage gate, and whitespace diff checks.

## Rollback Plan
1. Rollback trigger: runtime approval continuation or projection pack redaction blocks a previously valid supported path without a contract-backed reason.
2. Rollback steps: remove `create_directory` from the admitted approval-continuation set or disable the projection-pack outbound policy call while leaving the docs marked blocked.
3. Data/state recovery notes: no schema-destructive migration is introduced; SQLite migration tracking is additive and approval/projection changes are request-time behavior.

## Versioning Decision
- Version bump type: patch-level contract clarification with one bounded approval-family expansion.
- Effective version/date: 2026-04-25.
- Downstream impact: approval clients may observe `approval_required_tool:create_directory`; projection-pack clients may see redacted values and `policy_summary.outbound_policy_gate` metadata.
