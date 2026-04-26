# Contract Delta Proposal: NorthstarRefocus Phase 6 Outbound Policy Gate

## Summary
- Change title: Outbound policy gate redaction and configuration hardening
- Owner: Orket Core
- Date: 2026-04-25
- Affected contract(s): `docs/API_FRONTEND_CONTRACT.md`, `docs/SECURITY.md`, `CURRENT_AUTHORITY.md`, `docs/projects/archive/NorthstarRefocus/2026-04-25-OUTWARD-PIPELINE-CLOSEOUT/implementation_plan.md`

## Delta
- Current behavior: outward API surfaces call a minimal outbound policy gate that redacts built-in leak patterns, sensitive key leaves, email-like values, and ad hoc configured paths, but it has no documented environment/config-file policy surface and cannot preserve ledger truth if post-export redaction changes event payload bytes.
- Proposed behavior: the outbound gate supports configured PII field paths, forbidden regex patterns, and allowed output fields by event/surface type through environment variables or `ORKET_OUTBOUND_POLICY_CONFIG_PATH`; full ledger exports that would require event-payload redaction are represented as partial verified views with omitted-span hash anchors.
- Why this break is required now: Phase 6 is the active NorthstarRefocus hardening step and closes the policy-gate requirements without adding new approval features or changing ledger authority.

## Migration Plan
1. Compatibility window: existing `apply_outbound_policy_gate(payload, config)` callers remain supported; new configuration is additive.
2. Migration steps: operators can add policy config through env vars or JSON config file; clients consuming ledger exports must already handle `partial_view` from Phase 4.
3. Validation gates: focused unit and integration tests cover configured PII redaction, forbidden-pattern filtering, allowed-field filtering, non-mutation, deterministic filtering, API surface traversal, and ledger partial-view preservation.

## Rollback Plan
1. Rollback trigger: configured redaction mutates caller payloads, produces false full-ledger validity, or blocks operator payloads unexpectedly.
2. Rollback steps: remove the Phase 6 config loading and restore the previous minimal `apply_outbound_policy_gate()` internals while keeping existing call sites.
3. Data/state recovery notes: Phase 6 does not mutate stored run events, approvals, runs, or ledger hashes; rollback only changes response serialization behavior.

## Versioning Decision
- Version bump type: none in this worktree change.
- Effective version/date: 2026-04-25.
- Downstream impact: frontend and operator clients may see redacted fields or partial ledger exports when policy config is enabled.
